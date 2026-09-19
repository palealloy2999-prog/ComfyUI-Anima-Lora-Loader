# ANIMA LoRA Loader

[English README](README.md)

ComfyUIと[ComfyUI-Lora-Manager](https://github.com/willmiao/ComfyUI-Lora-Manager)が必要です。
このフォルダを `ComfyUI/custom_nodes` に置き、ComfyUIを再起動してブラウザを再読込します。

1. `loaders/anima` の **ANIMA LoRA Loader** を追加します。
2. MODELを接続します。CLIP接続は任意です。
3. 検索欄からLoRAを追加し、一覧でON/OFF・強度・CLIP強度・順番を変更します。
4. 通常は **Original Blocks Only** を使用します。

LoRAごとに28/40/52ブロックを判定し、28→40・28→52・40→52をメモリ内で変換します。
下位世代への適用は停止します。変換済みLoRAファイルは作りません。
処理結果は `remap_info`、適用したタグは `loaded_loras` に出力します。
`trigger_words` には、一覧で有効になっている各LoRAについて、LoRA Managerのメタデータから
取得したトリガーワードを一覧順に出力します。複数のトリガーワードは `,, ` で連結されます。
メタデータがない場合や取得に失敗した場合はそのLoRAを無視して処理を続けます。
CLIP未接続時のCLIP出力はNoneです。

**Copy To New Blocks** は追加ブロックへのコピー、**Blend Neighbor Blocks** は
前後の元ブロックの対応テンソルの平均です。両方とも実験機能です。
BlendはLoRA因子の平均であり、合成された差分の平均ではありません。
片側のみの場合はそのテンソルを使用し、形状等が合わない場合は停止します。

世代判定は最大ブロック番号+1です。一部ブロックだけを学習したLoRAでは誤判定する場合があります。
未知のLoRA世代は警告してそのまま適用し、未知のMODEL世代では停止します。
同名LoRAが複数ある場合はフォルダ込みの名前を使用してください。
検索タグの削除では一覧を削除しません。削除は一覧から行ってください。

52ブロック用マッピングは[参照元](https://github.com/shin131002/ComfyUI-Anima-Remap)の
推定復元版です。出典情報を同梱しています。LoRA Managerの一覧・検索Widgetを再利用していますが、
ライブラリ側の「loaderへ送信」は対象ノードが固定されているため、このノードでは検索欄を使います。
検証内容と制限は `VERIFICATION.md`、実装・出典の詳細は `README.md` を参照してください。


## install

```
cd custum_nodes
git clone https://github.com/palealloy2999-prog/ComfyUI-Anima-Lora-Loader
```
