# poe2-translation-kr

JavaScript lookup helpers and Korean translation data for Path of Exile 2
websites and browser integrations.

## Install

Install the package from GitHub:

```sh
npm install github:jun1bh1/poe2_translation_kr
```

This is a reusable ES module library, not a userscript: it exports functions
for a site-specific script or application to import, and does not run
automatically on a website.

```js
import { loadTranslator } from "poe2-translation-kr";

const translator = await loadTranslator(
  "https://raw.githubusercontent.com/jun1bh1/poe2_translation_kr/main/translations/",
);
```

`loadTranslator` fetches the published compact, word, base-item, item-category,
unique-item, character-class/ascendancy, and custom JSON files. Class and
ascendancy names are kept in `classes.json` with their source table names.
Pass `{ fetch }` to use a custom fetch implementation. HTTP and JSON parsing
errors are surfaced to the caller.

## Look up translations

Lookups return arrays because an English key can have multiple translations or
appear in more than one table. Use the `table` option when the site context
identifies a table.

```js
translator.translate("Hoghunt", { table: "uniqueitems" });
// [{
//   id: "Hoghunt",
//   ko: "돼지사냥",
//   table: "uniqueitems",
//   baseItem: "Felled Greatclub",
//   baseItemRecord: { id: "Felled Greatclub", ko: "쓰러진 대곤봉", ... },
//   itemClassRecord: { id: "Two Hand Mace", ko: "양손 철퇴", ... }
// }]

translator.reverseTranslate("돼지사냥", { table: "uniqueitems" });
translator.reverseTranslate("양손 철퇴", {
  table: "itemclasscategories",
});
```

Search Korean item categories and discover uniques whose base item belongs to
that category:

```js
const result = translator.search("양손 철퇴", { language: "ko" });
// result.matches includes "Two Hand Mace"
// result.relatedUniqueItems includes Hoghunt and other matching uniques
```

`findRelatedUniqueItems(text, { language: "ko" | "en" })` returns just those
related unique items. `search` defaults to English; `translate` searches
English-to-Korean, and `reverseTranslate` searches Korean-to-English.

## Custom translations

Add manual entries to `translations/custom.json` as an object of
English-to-Korean strings:

```json
{
  "Site-specific term": "사이트 전용 용어"
}
```

Custom entries participate in both lookup directions under the `custom` table.
The poe.ninja userscript also uses `translations/poe_ninja.json` for
site-specific interface labels; those labels are intentionally kept separate
from the shared translation library.

## Use locally

```js
import { createTranslator } from "poe2-translation-kr";
import compact from "./translations/translation_map_compact.json" with {
  type: "json"
};
import words from "./translations/words.json" with { type: "json" };
import baseitemtypes from "./translations/baseitemtypes.json" with {
  type: "json"
};
import itemclasscategories from "./translations/itemclasscategories.json" with {
  type: "json"
};
import uniqueitems from "./translations/uniqueitems.json" with { type: "json" };
import custom from "./translations/custom.json" with { type: "json" };

const translator = createTranslator({
  compact,
  words,
  baseitemtypes,
  itemclasscategories,
  uniqueitems,
  custom,
});
```

Run the focused test suite with `npm test`.
