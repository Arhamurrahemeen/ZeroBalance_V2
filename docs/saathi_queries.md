# Saathi — 10 pre-tested Urdu queries (demo scope)

Corpus: 16 synthetic snippets in `backend/app/saathi_corpus.json` (all marked مصنوعی ڈیمو —
invented for the demo, not real SBP/bank policy). Retrieval: multilingual MiniLM embeddings
in Qdrant, top-3. Answers: Groq, grounded in retrieved snippets only.

| # | Query (Urdu) | Expected snippet |
|---|---|---|
| 1 | دن کے اختتام پر کیش کیسے ملایا جائے؟ | EOD cash balancing |
| 2 | نوٹوں کی گنتی کیسے درج کروں؟ | Denomination count procedure |
| 3 | کتنے فرق پر منیجر کو رپورٹ کرنا ضروری ہے؟ | Variance reporting thresholds |
| 4 | کیش کم نکلے تو ذمہ داری کس کی ہے؟ | Shortage responsibility |
| 5 | ڈبل پوسٹنگ ہو جائے تو کیا کروں؟ | Duplicate posting correction |
| 6 | ریورسل کی منظوری کون دیتا ہے؟ | Reversal approval |
| 7 | جعلی نوٹ ملنے پر کیا کرنا چاہیے؟ | Counterfeit note handling |
| 8 | ٹیلر کے پاس زیادہ سے زیادہ کتنا کیش ہو سکتا ہے؟ | Teller drawer cash limit |
| 9 | والٹ میں کیش منتقل کرنے کا طریقہ کیا ہے؟ | Vault transfer dual custody |
| 10 | غلط اکاؤنٹ میں رقم چلی جائے تو کیا کریں؟ | Wrong account posting |

Each query is oracle-tested in `backend/tests/test_saathi.py`: the expected snippet must
appear in the top-3 retrieval results. Out of scope (LOCKED): corpus management UI, live
upload, queries beyond this demo set.
