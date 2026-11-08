/**
 * Google Sheet QUERY 公式自動檢查（Apps Script，免費，不需要 Google Cloud）
 *
 * 使用方式：
 *  1. 照 docs/google-sheet-query.md 第 1 節，把 data/sheets/events_flat.csv 匯入成「活動」工作表
 *     （匯入時保留勾選「將文字轉換成數字、日期和公式」，日期才會是日期格式）。
 *  2. 試算表選單「擴充功能」→「Apps Script」，把這個檔案全部內容貼上、取代原本的程式碼，按「儲存」。
 *  3. 上方函式選單選 checkAllQueries →「執行」。第一次會要求授權：選自己的帳號 →「進階」→「前往（不安全）」→「允許」。
 *     （這是 Google 對自己寫的程式的標準警告；程式只讀寫這份試算表，不會連到其他地方。）
 *  4. 執行完會多出 Q1～Q8 八個工作表（每個公式的結果）和「檢查結果」工作表。
 *     把「檢查結果」整張表複製（Ctrl+A、Ctrl+C）貼給晨嬡／Claude 確認。
 */

const SOURCE = '活動';

// 和 docs/google-sheet-query.md 的公式相同
const QUERIES = [
  ['Q1 各地區活動數',
   '=QUERY(活動!A:N, "select K, count(A) where A is not null group by K order by count(A) desc label K \'地區\', count(A) \'活動數\'", 1)'],
  ['Q2 各類別活動數與平均票價',
   '=QUERY(活動!A:N, "select C, count(A), avg(F) where A is not null group by C order by count(A) desc label C \'類別\', count(A) \'活動數\', avg(F) \'平均原價\'", 1)'],
  ['Q3 北部學生優惠300元以下',
   '=QUERY(活動!A:N, "select B, J, F, G where K = \'北部\' and H = \'是\' and G <= 300 order by G label B \'活動\', J \'縣市\', F \'原價\', G \'學生價\'", 1)'],
  ['Q4 今天到月底的活動',
   '=QUERY(活動!A:N, "select B, C, D, E, J where D <= date \'" & TEXT(EOMONTH(TODAY(), 0), "yyyy-mm-dd") & "\' and E >= date \'" & TEXT(TODAY(), "yyyy-mm-dd") & "\' order by E", 1)'],
  ['Q5 免費活動',
   '=QUERY(活動!A:N, "select B, C, J, D, E where F = 0 order by D", 1)'],
  ['Q6 熱門收藏前10名',
   '=QUERY(活動!A:N, "select B, C, N where N > 0 order by N desc limit 10 label B \'活動\', C \'類別\', N \'收藏數\'", 1)'],
  ['Q7 類別×地區樞紐',
   '=QUERY(活動!A:N, "select C, count(A) where A is not null group by C pivot K", 1)'],
  ['Q8 下拉選單查詢',
   '=QUERY(活動!A:N, "select B, C, J, D, E, F, G where K = \'" & B1 & "\' and C = \'" & B2 & "\' order by D", 1)'],
];

function checkAllQueries() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const source = ss.getSheetByName(SOURCE);
  if (!source) throw new Error('找不到「' + SOURCE + '」工作表，請先匯入 events_flat.csv 並把工作表改名為「活動」');
  const data = source.getDataRange().getValues();
  const header = data[0];
  const rows = data.slice(1).filter(r => r[0] !== '');

  // 1. 每個公式放進自己的工作表
  QUERIES.forEach(([name, formula], i) => {
    const sheet = resetSheet_(ss, 'Q' + (i + 1));
    if (i === 7) {  // Q8：下拉選單的條件先放固定值
      sheet.getRange('A1:B2').setValues([['地區', '北部'], ['類別', '展覽']]);
      sheet.getRange('A4').setFormula(formula);
    } else {
      sheet.getRange('A1').setFormula(formula);
    }
  });
  SpreadsheetApp.flush();

  // 2. 用程式自己算一次答案，和公式結果比對
  const col = name => header.indexOf(name);
  const C = { title: col('活動名稱'), price: col('原價'), region: col('地區'), saves: col('收藏數'), cat: col('類別') };
  const expectedRegion = {};
  rows.forEach(r => { expectedRegion[r[C.region]] = (expectedRegion[r[C.region]] || 0) + 1; });
  const expectedFree = rows.filter(r => r[C.price] === 0).length;
  const expectedTop = rows.filter(r => r[C.saves] > 0).sort((a, b) => b[C.saves] - a[C.saves]).slice(0, 10)
                          .map(r => r[C.saves]);
  const expectedNorthExhibit = rows.filter(r => r[C.region] === '北部' && r[C.cat] === '展覽').length;
  const dateType = rows.length ? Object.prototype.toString.call(rows[0][col('開始日期')]) : '';

  // 3. 讀回結果，寫入「檢查結果」
  const report = [['公式', '狀態', '結果列數', '說明', '前 3 列']];
  QUERIES.forEach(([name], i) => {
    const sheet = ss.getSheetByName('Q' + (i + 1));
    const start = i === 7 ? 4 : 1;
    const values = sheet.getRange(start, 1, Math.max(sheet.getLastRow() - start + 1, 1), Math.max(sheet.getLastColumn(), 1))
                        .getDisplayValues();
    const first = values[0][0];
    if (/^#(VALUE|N\/A|ERROR|REF|NAME)/.test(first)) {
      report.push([name, '✗ 公式錯誤', 0, first + '（滑鼠移到 Q' + (i + 1) + '!A' + start + ' 看錯誤訊息）', '']);
      return;
    }
    const body = values.slice(1).filter(r => r.some(v => v !== ''));
    let status = '✓', note = '';
    if (i === 0) {
      const got = {}; body.forEach(r => { got[r[0]] = Number(r[1]); });
      const wrong = Object.keys(expectedRegion).filter(k => got[k] !== expectedRegion[k]);
      status = wrong.length ? '✗ 數字不符' : '✓';
      note = '程式計算：' + JSON.stringify(expectedRegion) + (wrong.length ? '；不符：' + wrong.join('、') : '');
    } else if (i === 4) {
      status = body.length === expectedFree ? '✓' : '✗ 筆數不符';
      note = '程式計算免費活動 ' + expectedFree + ' 筆';
    } else if (i === 5) {
      const got = body.map(r => Number(r[2]));
      status = JSON.stringify(got) === JSON.stringify(expectedTop) ? '✓' : '✗ 排行不符';
      note = '程式計算收藏數：' + expectedTop.join(', ');
    } else if (i === 7) {
      status = body.length === expectedNorthExhibit ? '✓' : '✗ 筆數不符';
      note = '程式計算北部展覽 ' + expectedNorthExhibit + ' 筆';
    } else if (i === 3) {
      note = '開始日期欄的型態：' + dateType + (dateType === '[object Date]' ? '' : '（不是日期！匯入時要勾選轉換日期）');
      if (dateType !== '[object Date]') status = '✗ 日期沒有轉換';
    } else if (body.length === 0) {
      status = '！沒有資料'; note = '公式沒錯但查不到資料，可能是條件太嚴';
    }
    report.push([name, status, body.length, note, body.slice(0, 3).map(r => r.slice(0, 4).join(' | ')).join('\n')]);
  });

  const out = resetSheet_(ss, '檢查結果');
  out.getRange(1, 1, report.length, report[0].length).setValues(report);
  out.getRange(report.length + 2, 1).setValue(
    '資料列數：' + rows.length + '；檢查時間：' + new Date().toLocaleString('zh-TW') + '；試算表地區設定：' + ss.getSpreadsheetLocale());
  out.autoResizeColumns(1, 4);
  out.activate();
}

function resetSheet_(ss, name) {
  const existing = ss.getSheetByName(name);
  if (existing) ss.deleteSheet(existing);
  return ss.insertSheet(name);
}
