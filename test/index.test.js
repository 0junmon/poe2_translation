import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { createTranslator } from "../index.js";

const translationDirectory = new URL("../translations/", import.meta.url);

async function readJson(fileName) {
  return JSON.parse(
    await readFile(new URL(fileName, translationDirectory), "utf8"),
  );
}

async function createRealTranslator() {
  return createTranslator({
    compact: await readJson("translation_map_compact.json"),
    words: await readJson("words.json"),
    baseitemtypes: await readJson("baseitemtypes.json"),
    itemclasscategories: await readJson("itemclasscategories.json"),
    uniqueitems: await readJson("uniqueitems.json"),
    custom: await readJson("custom.json"),
  });
}

test("translates unique item names and resolves their base item and category", async () => {
  const translator = await createRealTranslator();
  const [hoghunt] = translator.translate("Hoghunt", { table: "uniqueitems" });

  assert.equal(hoghunt.ko, "돼지사냥");
  assert.equal(hoghunt.baseItemRecord.ko, "쓰러진 대곤봉");
  assert.equal(hoghunt.itemClassRecord.ko, "양손 철퇴");
});

test("reverse search returns item-class matches and related unique items", async () => {
  const translator = await createRealTranslator();
  const result = translator.search("양손 철퇴", { language: "ko" });

  assert.ok(
    result.matches.some(
      (match) =>
        match.table === "itemclasscategories" &&
        match.id === "Two Hand Mace",
    ),
  );
  assert.ok(
    result.relatedUniqueItems.some(
      (item) => item.id === "Hoghunt" && item.baseItem === "Felled Greatclub",
    ),
  );
});

test("custom object entries participate in both translation directions", () => {
  const translator = createTranslator({
    custom: { "Community Term": "커뮤니티 용어" },
  });

  assert.equal(translator.translate("Community Term")[0].ko, "커뮤니티 용어");
  assert.equal(
    translator.reverseTranslate("커뮤니티 용어")[0].id,
    "Community Term",
  );
});

test("reports all matches when an English term is ambiguous", () => {
  const translator = createTranslator({
    compact: [
      { id: "Shared", ko: "번역 A", table: "one" },
      { id: "Shared", ko: "번역 B", table: "two" },
    ],
  });

  assert.deepEqual(
    translator.translate("shared").map((match) => match.ko),
    ["번역 A", "번역 B"],
  );
});

test("searches Korean translation substrings across all tables", async () => {
  const translator = await createRealTranslator();
  const serle = String.fromCodePoint(0xc138, 0xb97c);
  const grit = String.fromCodePoint(0xadfc, 0xc131);
  const serleMatches = translator.searchKorean(serle);
  const gritMatches = translator.searchKorean(grit);

  assert.ok(
    serleMatches.some(
      (match) => match.id === "Serle's Grit" && match.ko.includes(grit),
    ),
  );
  assert.ok(
    gritMatches.some(
      (match) => match.id === "Serle's Grit" && match.ko.includes(grit),
    ),
  );
  assert.ok(
    translator
      .searchKorean(serle, { table: "uniqueitems" })
      .some((match) => match.id === "Serle's Grit"),
  );
});

test("rejects malformed translation records", () => {
  assert.throws(
    () =>
      createTranslator({
        compact: [{ id: "Missing fields" }],
      }),
    /must contain string id, ko, and table fields/,
  );
});

test("loads every published file and reports fetch failures", async () => {
  const filenames = new Set([
    "translation_map_compact.json",
    "words.json",
    "baseitemtypes.json",
    "itemclasscategories.json",
    "uniqueitems.json",
    "custom.json",
  ]);
  const translator = await (
    await import("../index.js")
  ).loadTranslator("https://example.test/translations", {
    fetch: async (url) => {
      const fileName = new URL(url).pathname.split("/").at(-1);
      assert.ok(filenames.has(fileName));
      return {
        ok: true,
        json: () => readJson(fileName),
      };
    },
  });
  assert.equal(
    translator.translate("Hoghunt", { table: "uniqueitems" })[0].ko,
    "돼지사냥",
  );

  await assert.rejects(
    () =>
      import("../index.js").then(({ loadTranslator }) =>
        loadTranslator("https://example.test/translations", {
          fetch: async () => ({
            ok: false,
            status: 404,
            statusText: "Not Found",
          }),
        }),
      ),
    /Failed to load .*: HTTP 404 Not Found/,
  );
});
