# poe2_translation

Path of Exile 2 한글 번역 데이터 저장소다. poe.ninja 크롬 확장이 이 데이터를
빌드 시 포함해서 사용한다(실행 중 외부 다운로드 없음).

## 작업을 이어받는 경우

- 코드·빌드 도구·인수인계 문서는 별도 저장소에 있다:
  `https://github.com/jun1bh1/poe2_extensions` (비공개)
- 그 저장소의 **`AGENTS.md` 0절(시작 체크리스트)** 부터 읽는다.
- 이 저장소는 `translations/**`만 Git으로 추적한다. `data/`(게임 덤프, `.csd`
  추출물, 백업)는 로컬 전용이라 GitHub에 없다. 다른 PC에서는 원본에서 직접 복사해야 한다.
- 번역 데이터 검사는 코드 저장소에서 실행한다:
  ```powershell
  $env:POBKR_ROOT = 'C:\Users\Administrator\Documents\poe2_translation'
  cd C:\Users\Administrator\Documents\poe2_extensions\pipeline
  npm run verify:data
  ```

## 구조

| 폴더 | 내용 |
| --- | --- |
| `translations/general/` | poe.ninja UI, 수동 키워드/오버라이드 (`poe_ninja.json`, `keyword.json`, `custom.json`) |
| `translations/items/` | 아이템 이름/분류 |
| `translations/names/` | 고유명사, 지역/퀘스트, 클래스 |
| `translations/lines/` | 모드/스킬/스탯/설명 문장 |
