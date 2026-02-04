# Parakeet-TDT-GUI: インテリジェント音声文字起こし＆字幕ワークステーション

<p align="center">
  <img src="https://img.shields.io/badge/Model-NVIDIA%20Parakeet-green" alt="Model">
  <img src="https://img.shields.io/badge/Framework-NeMo%20%2F%20Gradio-orange" alt="Framework">
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License">
</p>

<p align="center">
  <a href="./README_en.md">English</a>
  <a href="./README_ko.md">한국어</a> 
  <a href="./README.md">简体中文</a>
</p>

**Parakeet-TDT-GUI** は、強力なローカル型視聴覚処理ワークステーションです。**NVIDIA NeMo** フレームワークと **Parakeet-TDT** シリーズモデルをベースにしており、高速かつ高精度の音声認識（ASR）を提供するだけでなく、**LLM（大規模言語モデル）翻訳**、**インテリジェントな文分割**、そして**可視化された字幕校正エディタ**を統合しています。

本プロジェクトは、字幕制作者、動画クリエイター、語学学習者に「文字起こし・校正・翻訳・エクスポート」のワンストップソリューションを提供することを目指しています。

## ✨ 主な機能

### 1. 究極の文字起こし (ASR)
*   **マルチモデル対応**: NVIDIA 最新の Parakeet TDT シリーズモデルを統合：
    *   `0.6b-v2`: 英語認識において総合能力が最強。
    *   `0.6b-v3`: **20言語以上**（英/独/仏/露/日/西など）に対応。
    *   `ctc-110m`: 超軽量、低VRAM消費で極めて高速な推論が可能。
    *   `0.6b-ja`: **日本語**に特化して最適化された専用モデル。
*   **多形式エクスポート**: `SRT`, `VTT`, `ASS` (エフェクト字幕), `LRC` (歌詞), `TXT`, `JSON` の出力に対応。
*   **マイクロ秒単位の精度**: **単語レベル (Word-level)** および **文字レベル (Character-level)** のタイムスタンプ出力をサポートし、カラオケ字幕や精密な同期に最適です。
*   **スマートレイアウト**: インテリジェントな分割ロジックを内蔵しており、1行あたりの最大文字数を制限して、字幕が長くなりすぎるのを防ぎます。

### 2. LLM インテリジェント翻訳
*   **マルチモデル互換**: OpenAI 形式のインターフェース（**DeepSeek**, **ChatGPT**, **Claude** など）および Google Gemini ネイティブインターフェースと互換性があります。
*   **バイリンガル字幕**: 「原文＋訳文」の対訳字幕の生成をサポート。
*   **ズレ防止アルゴリズム**: ID-Mapping マッピング技術を採用し、大規模モデル翻訳時に発生しがちな行数の不一致やタイムラインのズレを完全に解決しました。
*   **高並列処理**: マルチスレッド並列翻訳をサポートし、長時間の動画処理速度を大幅に向上させました。

### 3. ビジュアル字幕エディタ
*   **校正テーブル**: Excel のようなインターフェースで、Web ページ上で直接タイムラインやテキストを修正できます。
*   **一括修正**: 「誤り-正解」の対照表を定義（例：「Parakeet」を「インコ」に統一するなど）し、全文を一括置換できます。
*   **校正メモリ**: 校正ルールを自動保存し、使うほどに使いやすくなります。

### 4. AI インテリジェント文分割 (Segmentation)
*   ASR が生成した改行のない長文テキストに対し、LLM の意味理解能力を利用してインテリジェントに分割を行い、元のタイムラインに自動的にマッチさせ、人間が読みやすい短文の字幕を生成します。

---

## 動作環境

*   **OS**: Windows / Linux
*   **Python**: 3.10 - 3.12
*   **GPU**: **4GB以上の VRAM** を搭載した NVIDIA グラフィックカードを推奨（CUDA 対応）。
    *   *注: GPU がない場合でも CPU モードで使用可能ですが、速度は遅くなります。*
*   **FFmpeg**: **必須インストール**。システム環境変数に設定してください（音声抽出に使用）。
### インストール前提条件: Windows 環境で依存関係のインストールに失敗する場合は、PCに **Visual Studio** がインストールされ、コンパイルが可能か確認してください。

---

## 🚀 インストールガイド (Windows)

### 方法1: バッチスクリプトを使用（初心者向け）

1.  **本プロジェクトをクローン/ダウンロード** します。
2.  **`install_dependencies.bat`** をダブルクリックして実行します。
    *   スクリプトが自動的に Python 仮想環境を作成します。
    *   必要なライブラリを自動的にインストールします。
3.  インストール完了後、**`launcher.bat`** をダブルクリックしてプログラムを起動します。

> **注意**: GPU 加速が必要な場合は、「方法2」を参考に PyTorch を手動インストールし、CUDA バージョンを一致させることを推奨します。

### 方法2: 手動コマンドラインインストール（推奨）

1.  **リポジトリのクローン:**
    ```bash
    git clone https://github.com/NINIYOYYO/NeMo-ASR-GUI.git
    cd NeMo-ASR-GUI.git
    ```

2.  **仮想環境の作成とアクティブ化:**
    ```bash
    python -m venv .venv
    # Windows:
    .\.venv\Scripts\activate
    # Linux/Mac:
    source .venv/bin/activate
    ```

3.  **PyTorch のインストール (重要: GPU ユーザーは特に注意!):**
    NVIDIA GPU を使用して処理を高速化したい場合（強く推奨）、**他の依存関係をインストールする前に、必ず CUDA 環境と互換性のある PyTorch バージョンを手動でインストールしてください。**
    *   `Win+R` キーを押して実行ウィンドウを開き、`CMD` と入力してターミナルに入り、以下を入力します：
    ```bash
    nvidia-smi
    ```
    Enter キーを押して CUDA Version を確認します。
    *   [PyTorch 公式サイトのインストールガイド](https://pytorch.org/get-started/locally/) にアクセスします。
    *   OS、パッケージマネージャー（`pip` 推奨）、計算プラットフォーム（例：CUDA 11.8, CUDA 12.1）、Python バージョンに合わせて正しいインストールコマンドを選択します。
    *   例えば、`pip` を使用し、システムが CUDA 12.1 環境の場合：
        ```bash
        pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        ```
    この手順をスキップしたり、NVIDIA GPU がない場合、後続の `nemo_toolkit` インストール時に CPU 専用の PyTorch がデフォルトでインストールされる可能性があります。

4.  **その他のプロジェクト依存関係のインストール:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **FFmpeg のインストール:**
    *   **Windows**: FFmpeg のコンパイル済みパッケージをダウンロードし、解凍して `bin` フォルダのパスをシステムの `Path` 環境変数に追加します。
    *   ターミナルを開き `ffmpeg -version` と入力し、出力が表示されればインストール成功です。

6.  **プログラムの起動:**
    ```bash
    python main.py
    ```
---    
## 📖 使用チュートリアル

### 1. モデルロード (Model Loading)
**"Model Settings" (モデル設定)** エリアに入ります：
*   **クラウドモデル**: モデルを選択（例：`nvidia/parakeet-tdt-0.6b-v2`）し、「Load」をクリックします。初回は自動的にダウンロードされます（約1-2GB）。
*   **ローカルモデル**: `.nemo` ファイルの絶対パスを入力し、「Load」をクリックします。

### 2. 字幕生成 (Transcription)
1.  動画/音声ファイルをアップロードします（一括処理対応）。
2.  **チャンク長 (Chunk Length)**: 60〜180秒を推奨。
3.  **出力形式**: 必要な形式にチェックを入れます（`srt` と `ass` 推奨）。
4.  **詳細オプション**:
    *   *Word/Char Level*: カラオケ効果が必要な場合にチェック。
    *   *Smart Split (スマート分割)*: オンにして「最大行幅」を設定（例：40文字）すると、長文を自動的に2行に分割します。
5.  **"Start Generation"** をクリックします。

### 3. 字幕編集 (Editing)
1.  **"Subtitle Edit"** タブで、生成された SRT ファイルをアップロードします。
2.  **一括校正**: 左側の「校正表」によくある間違いと正しい単語を入力し、「Batch Replace」をクリックします。
3.  **手動微調整**: 下の表で文字や時間を直接修正します。
4.  **"Save Subtitle File"** をクリックして修正版をエクスポートします。

### 4. AI 翻訳 (Translation)
1.  **"AI Translation"** タブに切り替えます。
2.  LLM 設定を入力します：
    *   **API Key**: OpenAI/DeepSeek/Gemini のキー。
    *   **Base URL**: 例 `https://api.deepseek.com` または `https://generativelanguage.googleapis.com/v1beta`。
    *   **Model**: 例 `deepseek-chat` または `gemini-3.0-flash`。
3.  **ターゲット言語**と**バイリンガル**設定を行います。
4.  開始をクリックすると、システムは並列翻訳を行い、新しいファイルを生成します。

### 5. AI 文分割 (Segmentation)
*   ASR で生成された字幕の文字は合っているが、タイムライン上で「一文が長すぎる」場合に適しています。
*   字幕をアップロードし、LLM を設定して開始すると、AI が意味に基づいてタイムラインを再分割します。

---
## 🖥️ インターフェース
!["Interface"](./README.assets/2.png)


## 📂 プロジェクト構造

```text
D:\PROGRAMING\PARAKEET-TDT-0.6B-V2-SRT-GUI
│  application.py           # アプリケーションのコアオーケストレーション
│  app_ui.py                # Gradio UI レイアウトとインタラクション
│  main.py                  # 起動エントリポイント
│  config.json              # ユーザー設定ファイル
│  
├─controllers/              # ビジネスロジックコントローラー
│      model_controller.py
│      subtitle_editor_controller.py
│      transcription_controller.py
│      translation_controller.py
│      
├─core/                     # コアサービス
│      asr_service.py       # NeMo モデル推論ラッパー
│      audio_processor.py   # FFmpeg 音声処理
│      post_processors.py   # 後処理戦略 (日本語最適化/文分割)
│      subtitle_generator.py# 字幕形式生成 (SRT/ASS/VTT等)
│      translation_service.py # LLM 翻訳と文分割サービス
│      
├─interfaces/               # インターフェース定義
├─locales/                  # 多言語インターフェース翻訳
├─subtitles/                # 出力ディレクトリ
│  ├─edited/                # 編集後の字幕
│  └─translated/            # 翻訳後の字幕
│      
└─utils/                    # ユーティリティ (ログ、設定、例外)
```


###  ⚠️ よくある質問 (FAQ)
***Q: 生成された字幕が文字化けしたり、タイムラインが重なったりするのはなぜですか？***

A: 言語が一致しないモデルを使用していないか確認してください。例えば、英語モデルで中国語の音声を文字起こしすると、予測不能な結果になります。0.6b-v3（多言語）または専用モデルを使用してください。

***Q: 翻訳機能で "429 Too Many Requests" エラーが出ます。***
A: API の呼び出し頻度制限です。画面上の "Concurrency (同時実行数)" スライダーを下げるか、"Chunk Size" を増やしてください。

***Q: プログラムが FFmpeg を見つけられないと表示されます。***
A: CMD で ffmpeg と入力してバージョン情報が表示されるか確認してください。インストールしたばかりの場合は、PC または IDE を再起動してください。

***Q: VRAM不足 (OOM) になった場合は？***

A: 1. 「音声チャンク長」を小さくします（例：30秒に設定）。2. より小さいモデル（ctc-110m）を使用してください。


### 🤝 貢献とライセンス
本プロジェクトは MIT ライセンスの下でオープンソース化されています。コアモデルの著作権は NVIDIA に帰属します。
Bug 報告や新機能の Pull Request を歓迎します！