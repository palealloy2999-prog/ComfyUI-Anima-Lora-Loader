# 検証記録 — 2026-09-19

配置先: `D:\AI_art\Data\Packages\ComfyUI2\custom_nodes\ComfyUI-Anima-Lora-Loader`

## 合格

- ComfyUIのvenv（PyTorch 2.14.0+cu130）でPythonテスト21件。
  世代判定、除外キー、3組の拡張変換、同世代、下位世代停止、コピー、平均、
  異なるテンソル形状のエラー、混在LoRA、順序、CLIP省略・強度0、パス解決を確認。
  ローダーのテストではファイル読込とComfyUI適用関数をモックしています。
- JavaScript同期テスト4件。追加・重複更新・ON/OFF保持・並べ替え・削除・強度同期、
  コールバック再入防止、保存値の復元、CLIP強度0の往復を確認。
  実行: `node --test --test-isolation=none tests/bridge.test.mjs`
  （通常のテスト子プロセス起動はこの検証環境でEPERMとなるため、同一プロセスで実行。）
- 配置済みパッケージを実際のComfyUI環境でimportし、ノード登録を確認。
- 実際の `ModelPatcher` / `load_lora_for_models` / `calculate_weight` を使用し、
  小さな合成MODEL・LoRAでCPU検証18通り。
  28/40/52同世代、28→40、28→52、40→52の各3モードについて、
  パッチ数、元MODEL未変更、適用後の重み差分を検証。
- Ruff検査・書式検査、JavaScript構文検査、空白エラー検査。

## 未確認

- 実際のANIMAチェックポイントによる画像生成・画質。
- ブラウザでの検索候補、プレビュー、ドラッグ、保存・再読込、タブ・サブグラフ操作。
  ポート8189・CPU・一時データ領域の検証サーバー起動を試みましたが、
  新ノード読込前のComfyUI起動処理で `OPENSSL_Uplink: no OPENSSL_Applink` により終了。
  通常のComfyUI設定は変更していません。

仕様書の「正常生成」「実UI操作」の完了条件は、以上の未確認項目があるため未達です。
実装と配置は完了していますが、v1の全受入条件を検証済みとはしていません。

## 依存実装の確認先

- [ComfyUI-Lora-Manager](https://github.com/willmiao/ComfyUI-Lora-Manager)
  `ee71d5c4993f29086b27fde1629a945ae48425bf`
- [ComfyUI-Anima-Remap](https://github.com/shin131002/ComfyUI-Anima-Remap)
  `3f9bb6ea56c52ae4ff559bc2490113c3b281751a`

52ブロック用マッピングは上流の推定復元データです。生成画像での検証は必要です。
pyproject.tomlはローカル配布用です。Registry公開・GitHub公開は行っていません。
