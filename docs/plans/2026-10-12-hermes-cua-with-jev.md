# hermes-cua-with-jev Implementation Plan

## Requirements

- 独立した Hermes プラグイン `hermes-cua-with-jev`。ブラウザとネイティブアプリを対象に、主モデルの毎手判断を減らし、操作時間・トークン消費を削減する。全操作での改善は保証せず計測する。
- TypeSafe API キーはユーザーが保有している前提。値をチャット・ログ・成果物に出さず、実行時に対象profileの秘密取得経路から取得する。キーを持っていることと現プロセスで読めることは区別する。
- Hermes core、他profile、既存ツール・スキルの実体は変更しない。既存CUAを無効化するかはユーザーへの提案段階であり、現時点では設定を変えない。

## Implementation Decisions

- ローカル `hermes-workspace-context` の薄い `__init__.py` + package 構成を採用する。root に `plugin.yaml`, `pyproject.toml`, `config.example.yaml`, `README.md`, `AGENTS.md`, `tests/`, `docs/`。本体は `hermes_cua_with_jev/`。秘密・実行記録はrepo外のprofile別runtime領域。
- GUI実装は既存 `cua-driver` を公開MCP経由で再利用する。Hermes coreの `tools.computer_use` ハンドラーを内部importしない。現在のCLIは0.30.4。スキルの記載バージョンとは別であり、利用可能なツール・引数は実機の公開schemaで確認する。
- Cua公式 `libs/cua-driver/examples/jev-use/` の候補選択・検証・持続MCP接続を先に調査し、利用可能な公開部品を優先する。コードを取り込む場合はlicenseとcommitを記録する。サンプルはブラウザfixture中心で、native対応や性能の認定ではない。
- 主モデル向けの入口は目的単位の少数ツールにする。ツール名・引数の確定は公式例のAPI調査後。目標、対象、入力値、完了条件、許可範囲、実行予算を受け取り、completed / need_help / blocked 等の短い結果と証拠参照を返す。
- ブラウザsemantic/DOMとnative AXをドライバーの公開機能で観測し、ローカルで構築した候補からJevが選ぶ。返却されたIDを照合し、モデル生成の任意コードや任意引数は実行しない。snapshot/tokenの失効、未知ID、権限拒否は実行前に停止。候補にできない視覚操作は主モデルに戻し、未確認のperception機能を前提にしない。
- 主モデルに全履歴・毎手スクショを返さない。困難時にのみ必要な観測を返す。復旧用の観測と単発操作も同じプラグイン経由で行える設計とし、既存CUAへの無限フォールバックを作らない。
- 同じデスクトップに対する並行制御を防ぐ。中断・時間/手数上限・部分実行を明示し、結果不明の入力や送信を自動再試行しない。既存ドライバーの承認を迂回しない。送信・削除・購入・前面操作等はユーザーの許可範囲を引き継ぐ。画面内容を指示や許可として扱わない。

## Tasks

- 実装開始時は計画書のみでGit未初期化。ユーザーはローカルGit作成・実装・検証・commitまでを承認、pushは保留。既存base commitはなく、独立レビューは新規リポジトリ全体を対象とする。
- 確認済みtest seam: plugin loader/公開tool、driver MCP境界、TypeSafe SDK境界。公開ツール契約・外部入出力・実機の事後状態を検証し、内部関数形状には依存しない。

- [ ] plugin registrationと設定: `plugin.yaml`, `__init__.py`, `hermes_cua_with_jev/plugin.py`, `config.py` を実装。対象profileでの発見と秘密非出力をテスト先行で検証する。
- [ ] driver / Jev接続と実行ループ: 公式例の実装とTypeSafeの現行SDK/APIを確認して `driver.py`, `jev.py`, `runner.py`, `tool_handlers.py` に必要最小限の責務を分ける。browser/native双方の観測・実行・独立した完了確認を実装する。MCPや選択モデルSDKを独自再実装しない。
- [ ] 公開ツールと専用skill: 通常実行と必要時の復旧を同一入口群に集約。READMEに対応範囲、送信データ、承認、障害時の挙動、実測値を記載する。
- [ ] 移行案: 検証後にdefault profileの旧 `computer_use` toolsetと重複する `computer-use` / `cua-driver` skillを非表示にする案を提示。削除せず既存の設定経路を使用する。browser/agent-deviceなど異なる用途は一括無効化しない。新しいセッションでのtool/skill一覧とロールバックを検証する。設定変更は別途了承後。

## Final Validation

- [ ] 新規pluginのテスト設定に `python -m pytest -q` を用意し、候補ID照合、失効token、承認待ち、中断、部分実行、秘密非出力、runtime/profile分離、結果サイズを検証する。
- [ ] 隔離したHermes homeで実loaderによる発見・tool登録・toolset無効化時の非公開を検証する。本番gatewayの再起動は行わない。
- [ ] 実TypeSafe APIとインストール済みdriverでブラウザfixture、および無害なnative GUIタスクを実行し、事後状態で成功を確認する。mock成功をlive成功として扱わない。OS承認等の不足時は停止して必要条件を報告する。
- [ ] 同一タスク・同一成功条件で従来方式と比較し、wall time、主モデル/JeVの入力・出力usage、復旧回数、成功率を記録する。取得不能なusageは未計測とし、推定値を実測として扱わない。
- [ ] 独立レビューで複数セッションの排他・承認境界・driver契約を確認する。必要な修正後に関連テストを再実行する。

## Checkpoint publication

ユーザーは安全性・排他範囲の判断を後回しにし、現状を `ryonakae/hermes-cua-with-jev` にcommit-pushするよう明示依頼。以前のpush保留を今回のチェックポイント保存に限って解除する。レビュー通過・実装完了・有効化を意味しない。未解決事項をREADMEとレビュー記録に残し、計画はarchiveしない。修正・比較計測は保留。

## Current verification / pause

- 専用 `.venv` で19テスト成功。SDK0.7.4を使用。native/browserのclick/type候補、observe/run/step/discover、MCP schema照合、refusal停止、SDK usage None対応、host-wide flockと未確認操作marker、profile別receiptを実装済み。ただし要件全体の検証・commitは未完了。
- 実TypeSafe API: jev-1.13.0でsave選択成功（331 input /31 output tokens、0.272秒）。実MCP接続とlist_windows成功。キーは非表示でstdin経由。
- 実native fixture: ユーザーの画面ロック解除後、同じ.appからAX要素取得に成功。最初のクリック後は結果用static labelが取得対象外でeffect_unverifiedだったため、fixtureのStatusをAXTextFieldへ変更。終了済みfixtureの未確認markerをlease内で解消し、再実行はcompleted、1手、5.720秒、Jev464 input/33 output tokens（1 call）。native fixtureはfinallyで終了。receipt: `~/.hermes/cache/scratch/jev-live-receipts/d5408fc53bdf4f06ae3d8dec3381dee4.json`。
- 実browser fixture: driver-ownedの隔離Chromeには非表示の補助windowも列挙されていた。fixture用の表示中about:blankウィンドウへ絞り、再実行はcompleted、1手、4.091秒、Jev460 input/33 output tokens（1 call）。双方ともfresh snapshotのStatus=Doneで成功を確認。隔離ブラウザの終了状態は未確認（MCP sessionは閉じた）。
- 残り: 安全性修正、比較計測、中断・秘密非出力等の追加テスト、README/AGENTS、再レビュー、local commit。`deleg_e1952b16` は完了。実loader/toolset公開・非公開/A→B→A分離テストを親が再実行し、合計21 passed in 2.95s。予備レビューは不合格で、入力値の外部送信、対象再検証、unknown結果、既知拒否後のmarker、子プロセス回収の5項目を修正対象として記録（`docs/review-2026-10-12.md`）。排他がplugin間に限定される点はユーザー確認待ち。driver承認契約は追加調査が必要。修正前の判断待ちで、まだproduction修正なし。
- ユーザーはレビュー後の従来方式比較を明示依頼。安全性修正と再レビュー通過後、同じ初期状態・成功条件でbrowser/nativeを比較する。既存の時間はrunner単独の実測であり、従来方式比較や主モデルtoken削減率は未計測。設定有効化・旧CUA無効化・gateway再起動・pushはしていない。
- 公式参照: Cua `43a76de6f8dea32b7f76a5b0b47e33303b0c405f` のjev-use、TypeSafe SDK `e70bf99a89f27102247613bcd5d1aa8923a1cda9`。調査結果受領済み、driver_env.pyとsources.pyを親で確認。コピーした実装コードはなし。

## References

- ローカル構成: `~/.hermes/plugins/hermes-workspace-context/{__init__.py,plugin.yaml,pyproject.toml,workspace_context/}`
- ローカルCUA入口: `~/.hermes/hermes-agent/tools/computer_use_tool.py`
- スキル非表示: `hermes_cli/skills_config.py` の `skills.disabled` / `skills.platform_disabled`
- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- https://github.com/trycua/cua/pull/3916
- https://docs.typesafe.ai/introduction
- https://cua.ai/docs/cua-driver
- ユーザー参考記事: https://zenn.dev/snaka0213/articles/06f5d9304d549c

各タスクは対応する検証が成功してから完了にする。実装中の軽微な差分と検証結果は該当箇所へ反映し、要件、対象外、公開契約の変更はユーザーへ確認する。最終確認では有効な検証結果を再利用し、計画と実際の変更が一致することを確認する。必要な検証と実装側の必須レビューが通ったら、計画を同名のまま `docs/plans/archived/` へ移す。
