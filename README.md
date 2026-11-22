# 일본 신고가 근접 · 시총 상위 페이지

스크롤(또는 방향키)로 넘기며 보는 한 장짜리 페이지입니다.
주가는 매일 자동 갱신되고, 분기 실적과 소개 문구는 `data/companies.json` 한 파일에 들어 있습니다.

## 설치 (한 번만)

1. GitHub에서 새 리포를 만들고(공개 리포), 이 폴더의 파일을 전부 올립니다.
   `.github/workflows/update.yml` 까지 폴더 구조 그대로 올라가야 합니다.
2. 리포 Settings → Pages → Source 를 **Deploy from a branch**, Branch 를 **main / (root)** 로 저장합니다.
3. 리포 Settings → Actions → General → Workflow permissions 를 **Read and write permissions** 로 저장합니다.
4. Actions 탭 → **update-prices** → **Run workflow** 를 눌러 첫 주가 수집을 실행합니다.
5. 1~2분 뒤 `https://<계정>.github.io/<리포이름>/` 에서 확인합니다.

이후에는 평일 16:25(일본 시간)에 주가가 자동으로 갱신됩니다.

## 파일

| 파일 | 역할 | 수정 주체 |
|---|---|---|
| `index.html` | 화면 | 건드릴 필요 없음 |
| `data/companies.json` | 종목 목록, 소개, 최근 6개 분기 실적 | 실적 시즌마다 교체 |
| `data/prices.json` | 1년치 일봉과 수익률 | 자동 (Actions) |
| `pipeline/build.py` | 야후 주가 수집 | 건드릴 필요 없음 |
| `.github/workflows/update.yml` | 자동 실행 일정 | 건드릴 필요 없음 |

## 분기 실적 갱신

`data/companies.json` 을 새 파일로 덮어쓰면 됩니다. 올리는 즉시 주가 수집도 다시 돌고 페이지에 반영됩니다.

## 알아둘 점

- GitHub Pages 주소는 링크를 아는 사람이면 누구나 열 수 있습니다. 검색엔진 수집은 막아 두었지만(noindex) 접근 제한은 아닙니다.
- 특정 종목으로 바로 가는 링크: 주소 뒤에 `#co-종목코드` (예: `#co-9983`).
- 시총은 2026-11-20 스냅샷에 주가 변동률을 곱한 추정치입니다. 주식분할이 있으면 `snap_price` 를 고쳐야 합니다.
- 수집이 실패한 종목은 이전 값을 유지합니다. 전 종목이 실패하면 Actions 가 실패로 표시되고 기존 데이터는 그대로 남습니다.
- 매출비중 문구는 근사치입니다. 분기 실적 수치는 株探(kabutan) 3개월 결산 실적 기준입니다.
