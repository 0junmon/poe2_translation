import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


COMPACT_TABLE_ID_FIELDS = {
    "activeskills": {"DisplayedName"},
    "baseitemtypes": {"Name"},
    "buffdefinitions": {"Name"},
    "grantedeffectlabels": {"Text"},
    "keywordpopups": {"Term"},
    "mods": {"Name"},
    "monstervarieties": {"Name"},
    "npcs": {"Name"},
    "passiveskills": {"Name"},
    "supportgemfamily": {"Name"},
    "words": {"Text2"},
}
MOD_DISPLAY_NAME_PATTERN = re.compile(r">\{([^{}]+)\}")
BRACKETED_TERMS_PATTERN = re.compile(r"^\[(.*)\]$")
COMPACT_TABLES_KEPT_SEPARATE = {
    "baseitemtypes",
    "itemclasscategories",
    "uniqueitems",
    "words",
}


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError(f"Expected a JSON array of objects in {path}")
    return data


def row_identity(
    table_name: str, row: dict[str, Any]
) -> tuple[str, dict[str, Any] | None] | None:
    row_id = row.get("Id")
    if isinstance(row_id, str) and row_id:
        return row_id, None

    if table_name == "words":
        wordlist = row.get("Wordlist")
        wordlist_id = wordlist.get("Id") if isinstance(wordlist, dict) else None
        hash32 = row.get("HASH32")
        if isinstance(wordlist_id, str) and isinstance(hash32, int):
            match_key = {"Wordlist.Id": wordlist_id, "HASH32": hash32}
            return f"Wordlist/{wordlist_id}/HASH32/{hash32}", match_key
    return None


def index_by_id(
    rows: list[dict[str, Any]], table_name: str
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        identity = row_identity(table_name, row)
        if identity is not None:
            grouped[identity[0]].append(row)
    duplicates = {row_id for row_id, matches in grouped.items() if len(matches) > 1}
    return (
        {row_id: matches[0] for row_id, matches in grouped.items() if len(matches) == 1},
        duplicates,
    )


def item_class_names(rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        row["Id"]: row["Name"]
        for row in rows
        if isinstance(row.get("Id"), str)
        and isinstance(row.get("Name"), str)
        and row["Id"]
    }


def item_class_id(row: dict[str, Any], item_classes: list[dict[str, Any]]) -> str | None:
    reference = row.get("ItemClass")
    if not isinstance(reference, dict) or reference.get("TableName") != "ItemClasses":
        return None
    row_index = reference.get("RowIndex")
    if not isinstance(row_index, int) or isinstance(row_index, bool):
        return None
    if row_index < 0 or row_index >= len(item_classes):
        return None
    class_id = item_classes[row_index].get("Id")
    return class_id if isinstance(class_id, str) else None


def translated_fields(
    english: dict[str, Any], korean: dict[str, Any]
) -> dict[str, dict[str, str]]:
    translations: dict[str, dict[str, str]] = {}
    for key, english_value in english.items():
        korean_value = korean.get(key)
        if (
            key != "Id"
            and isinstance(english_value, str)
            and isinstance(korean_value, str)
            and english_value.strip()
            and korean_value.strip()
            and english_value != korean_value
        ):
            translations[key] = {"en": english_value, "ko": korean_value}
    return translations


def shared_context(english: dict[str, Any], korean: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for key, value in english.items():
        if (
            key == "Id"
            or key.startswith("_")
            or key.startswith("HASH")
            or value is None
            or value == ""
        ):
            continue
        if isinstance(value, (str, int, float, bool)) and value == korean.get(key):
            context[key] = value
    return context


def build_map(balance_dir: Path, tables: set[str] | None) -> tuple[dict[str, Any], Counter[str]]:
    korean_dir = balance_dir / "korean"
    english_item_classes = load_rows(balance_dir / "itemclasses.json")
    korean_item_classes = load_rows(korean_dir / "itemclasses.json")
    english_class_names = item_class_names(english_item_classes)
    korean_class_names = item_class_names(korean_item_classes)

    table_files = sorted(balance_dir.glob("*.json"))
    if tables is not None:
        requested = {f"{table.lower()}.json" for table in tables}
        table_files = [path for path in table_files if path.name.lower() in requested]
        missing = requested - {path.name.lower() for path in table_files}
        if missing:
            raise FileNotFoundError(
                "Table JSON not found in the English balance folder: "
                + ", ".join(sorted(missing))
            )

    entries: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for english_path in table_files:
        korean_path = korean_dir / english_path.name
        if not korean_path.is_file():
            counts["missing_korean_table"] += 1
            continue

        english_rows = load_rows(english_path)
        korean_rows = load_rows(korean_path)
        table_name = english_path.stem
        english_by_id, english_duplicates = index_by_id(english_rows, table_name)
        korean_by_id, korean_duplicates = index_by_id(korean_rows, table_name)
        ambiguous_ids = english_duplicates | korean_duplicates
        counts["ambiguous_ids"] += len(ambiguous_ids)

        for english in english_rows:
            identity = row_identity(table_name, english)
            if identity is None:
                continue
            row_id = identity[0]
            if row_id in ambiguous_ids or row_id not in korean_by_id:
                continue
            korean = korean_by_id[row_id]
            translations = translated_fields(english, korean)
            if not translations:
                continue

            context = shared_context(english, korean)
            class_id = item_class_id(english, english_item_classes)
            if class_id is not None:
                class_info: dict[str, str] = {"id": class_id}
                if class_id in english_class_names:
                    class_info["en"] = english_class_names[class_id]
                if class_id in korean_class_names:
                    class_info["ko"] = korean_class_names[class_id]
                context["itemClass"] = class_info

            entry: dict[str, Any] = {
                "table": table_name,
                "id": row_id,
                "translations": translations,
                "context": context,
            }
            if table_name == "activeskills":
                english_name = english.get("DisplayedName")
                korean_name = korean.get("DisplayedName")
                if isinstance(english_name, str) and isinstance(korean_name, str):
                    entry["displayName"] = {
                        "en": english_name,
                        "ko": korean_name,
                    }
            identity = row_identity(table_name, english)
            if identity is not None and identity[1] is not None:
                entry["matchKey"] = identity[1]
            entries.append(entry)
            counts["entries"] += 1
            counts[f"table:{table_name}"] += 1

    return (
        {
            "formatVersion": 1,
            "languages": {"en": "English", "ko": "Korean"},
            "entries": entries,
        },
        counts,
    )


def add_compact(
    compact: list[dict[str, Any]],
    table_name: str,
    english: str,
    korean: str,
    item_class: str | None = None,
) -> None:
    if not english.strip() or not korean.strip() or english == korean:
        return
    entry: dict[str, Any] = {
        "id": english,
        "ko": korean,
        "table": table_name,
    }
    if item_class is not None:
        entry["itemClass"] = item_class
    compact.append(entry)


def add_long(
    long_translations: list[dict[str, Any]],
    table_name: str,
    row_id: str,
    field: str,
    english: str,
    korean: str,
    source_id: str | None = None,
) -> None:
    entry: dict[str, Any] = {
        "id": row_id,
        "field": field,
        "en": english,
        "ko": korean,
        "table": table_name,
    }
    if source_id is not None:
        entry["sourceId"] = source_id
    long_translations.append(entry)


def split_bracketed_terms(value: str) -> list[str] | None:
    match = BRACKETED_TERMS_PATTERN.fullmatch(value.strip())
    if match is None:
        return [value.strip()] if value.strip() else None
    return [term.strip() for term in match.group(1).split("|")]


def item_category_terms(english: str, korean: str) -> list[tuple[str, str]]:
    english_terms = split_bracketed_terms(english)
    korean_terms = split_bracketed_terms(korean)
    if english_terms is None or korean_terms is None:
        return []

    pair_count = min(len(english_terms), len(korean_terms))
    if len(english_terms) == len(korean_terms):
        return list(zip(english_terms, korean_terms))
    pairs = [
        (english_terms[-offset], korean_terms[-offset])
        for offset in range(1, pair_count + 1)
    ]
    return list(reversed(pairs))


def split_translation_map(
    translation_map: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    compact: list[dict[str, Any]] = []
    long_translations: list[dict[str, Any]] = []

    for entry in translation_map["entries"]:
        table_name = entry["table"]
        id_fields = COMPACT_TABLE_ID_FIELDS.get(table_name)
        if id_fields is None and table_name != "itemclasscategories" and table_name != "flavourtext":
            continue
        if table_name == "words" and entry.get("matchKey", {}).get(
            "Wordlist.Id"
        ) != "UNIQUE_ITEM":
            continue

        item_class = entry.get("context", {}).get("itemClass", {}).get("id")
        display_name = entry.get("displayName")
        if table_name == "activeskills" and isinstance(display_name, dict):
            compact_id = display_name.get("en", entry["id"])
        elif table_name == "buffdefinitions":
            compact_id = entry["translations"].get("Name", {}).get("en", entry["id"])
        elif table_name == "passiveskills":
            compact_id = entry["translations"].get("Name", {}).get("en", entry["id"])
        elif table_name == "mods":
            english_name = entry["translations"].get("Name", {}).get("en", entry["id"])
            korean_name = entry["translations"].get("Name", {}).get("ko", "")
            english_label = MOD_DISPLAY_NAME_PATTERN.search(english_name)
            korean_label = MOD_DISPLAY_NAME_PATTERN.search(korean_name)
            if english_label is not None and korean_label is not None:
                add_compact(
                    compact,
                    table_name,
                    english_label.group(1),
                    korean_label.group(1),
                )
                add_long(
                    long_translations,
                    table_name,
                    english_label.group(1),
                    "Name",
                    english_name,
                    korean_name,
                    entry["id"],
                )
                continue
            compact_id = english_name
        else:
            compact_id = entry["id"]

        if table_name == "itemclasscategories":
            english_text = entry["translations"].get("Text", {}).get("en")
            korean_text = entry["translations"].get("Text", {}).get("ko")
            if english_text is None or korean_text is None:
                continue
            for english_term, korean_term in item_category_terms(
                english_text, korean_text
            ):
                add_compact(
                    compact,
                    table_name,
                    english_term,
                    korean_term,
                )
            continue

        for field, values in entry["translations"].items():
            english = values["en"]
            korean = values["ko"]
            if table_name == "flavourtext" or id_fields is None or field not in id_fields:
                long_id = compact_id
                add_long(
                    long_translations,
                    table_name,
                    long_id,
                    field,
                    english,
                    korean,
                    entry["id"] if long_id != entry["id"] else None,
                )
                continue

            add_compact(
                compact,
                table_name,
                english,
                korean,
                item_class if table_name == "baseitemtypes" else None,
            )

    canonical_category_pairs = {
        (entry["id"].casefold(), entry["ko"].casefold())
        for entry in compact
        if entry["table"] == "itemclasscategories"
    }

    deduplicated: list[dict[str, Any]] = []
    seen_translation_pairs: set[tuple[str, str, str]] = set()
    for entry in compact:
        pair = (entry["id"].casefold(), entry["ko"].casefold())
        if (
            entry["table"] != "itemclasscategories"
            and pair in canonical_category_pairs
        ):
            continue
        scoped_pair = (entry["table"], pair[0], pair[1])
        if scoped_pair in seen_translation_pairs:
            continue
        seen_translation_pairs.add(scoped_pair)
        deduplicated.append(entry)

    return deduplicated, long_translations


def build_unique_item_entries(balance_dir: Path) -> list[dict[str, Any]]:
    english_crafts = load_rows(balance_dir / "expedition2verisiumcrafts.json")
    english_words = load_rows(balance_dir / "words.json")
    korean_words = load_rows(balance_dir / "korean" / "words.json")
    english_base_items = load_rows(balance_dir / "baseitemtypes.json")

    korean_words_by_id, ambiguous_word_ids = index_by_id(korean_words, "words")

    def resolve_reference(
        row: dict[str, Any],
        field: str,
        table_name: str,
        rows: list[dict[str, Any]],
        source_index: int,
    ) -> dict[str, Any]:
        reference = row.get(field)
        if (
            not isinstance(reference, dict)
            or reference.get("TableName") != table_name
            or not isinstance(reference.get("RowIndex"), int)
            or isinstance(reference.get("RowIndex"), bool)
            or not 0 <= reference["RowIndex"] < len(rows)
        ):
            raise ValueError(
                f"Invalid {field} reference in expedition2verisiumcrafts "
                f"row {source_index}"
            )
        return rows[reference["RowIndex"]]

    unique_items: dict[str, dict[str, Any]] = {}
    for source_index, craft in enumerate(english_crafts):
        english_unique = resolve_reference(
            craft, "UniqueName", "Words", english_words, source_index
        )
        unique_identity = row_identity("words", english_unique)
        wordlist = english_unique.get("Wordlist")
        if (
            unique_identity is None
            or unique_identity[0] in ambiguous_word_ids
        ):
            raise ValueError(
                f"Invalid or ambiguous unique name in expedition2verisiumcrafts "
                f"row {source_index}"
            )
        if not isinstance(wordlist, dict) or wordlist.get("Id") != "UNIQUE_ITEM":
            continue

        english_unique_name = english_unique.get("Text")
        korean_unique = korean_words_by_id.get(unique_identity[0])
        korean_unique_name = (
            korean_unique.get("Text2") if korean_unique is not None else None
        )
        if not isinstance(english_unique_name, str) or not isinstance(
            korean_unique_name, str
        ):
            raise ValueError(
                f"Missing unique name translation for expedition2verisiumcrafts "
                f"row {source_index}"
            )

        item = unique_items.setdefault(
            unique_identity[0],
            {
                "id": english_unique_name,
                "ko": korean_unique_name,
                "baseItems": {},
                "upgradedBaseItemIds": set(),
            },
        )
        original_base = resolve_reference(
            craft, "OriginalBaseType", "BaseItemTypes", english_base_items, source_index
        )
        new_base = resolve_reference(
            craft, "NewBaseType", "BaseItemTypes", english_base_items, source_index
        )
        original_base_id = original_base.get("Id")
        new_base_id = new_base.get("Id")
        if not isinstance(original_base_id, str) or not isinstance(new_base_id, str):
            raise ValueError(
                f"Missing base item ID in expedition2verisiumcrafts row {source_index}"
            )
        item["baseItems"].setdefault(original_base_id, original_base)
        if original_base_id != new_base_id:
            item["upgradedBaseItemIds"].add(new_base_id)

    entries: list[dict[str, Any]] = []
    for item in unique_items.values():
        base_items = item["baseItems"]
        base_item_ids = [
            base_item_id
            for base_item_id in base_items
            if base_item_id not in item["upgradedBaseItemIds"]
        ] or list(base_items)

        for base_item_id in base_item_ids:
            english_base = base_items[base_item_id]
            english_base_name = english_base.get("Name")
            if not isinstance(english_base_name, str):
                raise ValueError(f"Missing base item name for {base_item_id}")
            entries.append(
                {
                    "id": item["id"],
                    "ko": item["ko"],
                    "table": "uniqueitems",
                    "baseItem": english_base_name,
                }
            )

    return entries


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def write_table_files(entries: list[dict[str, Any]], directory: Path) -> int:
    entries_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        entries_by_table[entry["table"]].append(entry)

    directory.mkdir(parents=True, exist_ok=True)
    expected_files = {f"{table_name}.json" for table_name in entries_by_table}
    for existing_file in directory.glob("*.json"):
        if existing_file.name not in expected_files:
            existing_file.unlink()

    for table_name, table_entries in sorted(entries_by_table.items()):
        write_json(directory / f"{table_name}.json", table_entries)
    return len(entries_by_table)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match English and Korean PoE balance JSON records by their shared Id."
    )
    parser.add_argument(
        "--balance-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "data" / "balance",
        help="Folder containing English JSON files and the korean subfolder.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "translations" / "translation_map.json",
        help="Destination JSON file.",
    )
    parser.add_argument(
        "--tables",
        help="Optional comma-separated table names, e.g. monstervarieties,baseitemtypes.",
    )
    args = parser.parse_args()
    selected_tables = (
        {name.strip() for name in args.tables.split(",") if name.strip()}
        if args.tables
        else None
    )
    result, counts = build_map(args.balance_dir, selected_tables)
    compact, _long_translations = split_translation_map(result)
    unique_item_entries = build_unique_item_entries(args.balance_dir)
    compact.extend(unique_item_entries)

    compact_output = args.output.with_name(f"{args.output.stem}_compact{args.output.suffix}")
    compact_combined = [
        entry
        for entry in compact
        if entry["table"] not in COMPACT_TABLES_KEPT_SEPARATE
    ]
    compact_separate = [
        entry
        for entry in compact
        if entry["table"] in COMPACT_TABLES_KEPT_SEPARATE
    ]
    write_json(compact_output, compact_combined)
    compact_entries_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in compact_separate:
        compact_entries_by_table[entry["table"]].append(entry)
    for table_name, table_entries in sorted(compact_entries_by_table.items()):
        write_json(compact_output.parent / f"{table_name}.json", table_entries)

    print(f"Wrote {len(compact_combined)} combined translations to {compact_output}")
    print(f"Wrote {len(unique_item_entries)} unique-to-base item links")
    print(
        f"Wrote {len(compact_entries_by_table)} separate table files "
        f"to {compact_output.parent}"
    )
    print(f"Skipped ambiguous IDs: {counts['ambiguous_ids']}")
    print(f"English tables without Korean counterparts: {counts['missing_korean_table']}")


if __name__ == "__main__":
    main()
