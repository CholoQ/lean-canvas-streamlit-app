import streamlit as st
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import sys

# --- Streamlit ページ設定 (最初に呼び出す) ---
# ページタイトルとレイアウトを設定
st.set_page_config(page_title="Lean Canvas Generator", layout="wide")
st.title("Lean Canvas & Feedback Generator 🚀")
st.caption("アイデアのコア情報を入力し、AIと共にリーンキャンバスを作成・改善しましょう。")

# --- APIキーとモデルの設定 ---
# SecretsからAPIキーを読み込む試み（デプロイ用）なければ環境変数から読み込む（ローカル用）
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# APIキーがない場合はエラーメッセージを表示してアプリを停止
if not api_key:
    st.error("⚠️ APIキーが設定されていません。StreamlitのSecretsまたは環境変数に `GEMINI_API_KEY` を設定してください。")
    st.stop()

# Geminiクライアントの初期化
try:
    genai.configure(api_key=api_key)
    # 使用するモデルを選択 (Flashは高速・低コスト、Proはより高性能)
    model_name = 'gemini-1.5-flash-latest'
    model = genai.GenerativeModel(model_name)
    # st.success(f"Gemini ({model_name}) への接続準備完了！") # 任意：接続確認メッセージ
except Exception as e:
    st.error(f"❌ Geminiモデルの初期化中にエラーが発生しました: {e}")
    st.stop() # エラーが発生したらアプリを停止

# --- Session State の初期化 ---
# ユーザーの入力やAPIからの結果をアプリの再実行後も保持するために使用
if 'user_inputs' not in st.session_state:
    st.session_state.user_inputs = {} # ユーザーの初期入力を保持
if 'canvas_draft' not in st.session_state:
    st.session_state.canvas_draft = "" # 生成された最初のドラフトを保持
if 'feedback' not in st.session_state:
    st.session_state.feedback = ""    # 生成されたフィードバックを保持
if 'revised_canvas' not in st.session_state:
    st.session_state.revised_canvas = "" # 生成された改訂版を保持


# --- 安全設定 ---
# API呼び出し時に共通して使用する安全設定
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

# --- UIセクション ---

# --- 1. コア情報入力 ---
st.header("1. アイデアのコア情報を入力")
st.markdown("以下の項目について、具体的な情報を入力してください。")

# フォームを使って複数の入力をグループ化し、ボタンで一括送信
with st.form("lean_canvas_input_form"):
    questions = {
        "ターゲット顧客": "[顧客セグメント] あなたが最初に価値を届けたい具体的な顧客は誰ですか？",
        "顧客の課題": "[課題] その顧客が抱えている最も重要な課題は何ですか？",
        "提供する解決策": "[ソリューション] あなたの技術やアイデアは、その課題を具体的にどう解決しますか？",
        "コア技術": "[ソリューション/優位性] アイデアの中心となる技術やアプローチは何ですか？ (任意)",
        "既存比較と優位性": "[独自の価値提案/優位性] 既存の解決策と比べて、あなたのアイデアは何がどう優れていますか？"
    }
    # フォーム内にテキストエリアを配置
    for key, question in questions.items():
        st.session_state.user_inputs[key] = st.text_area(
            question,
            value=st.session_state.user_inputs.get(key, ""), # 前回入力があれば表示
            height=100, # テキストエリアの高さ
            key=f"input_{key}" # 各ウィジェットにユニークなキーを設定
        )

    # フォーム送信ボタン
    submitted = st.form_submit_button("🚀 Lean Canvas ドラフト生成")

    # ボタンがクリックされた場合の処理
    if submitted:
        # 新しいドラフト生成前に以前の生成結果をクリア
        st.session_state.canvas_draft = ""
        st.session_state.feedback = ""
        st.session_state.revised_canvas = ""

        # 簡単な必須項目チェック
        required_keys = ["ターゲット顧客", "顧客の課題", "提供する解決策", "既存比較と優位性"]
        if not all(st.session_state.user_inputs.get(key) for key in required_keys):
             st.warning("⚠️ 必須項目（ターゲット顧客、顧客の課題、提供する解決策、既存比較と優位性）をすべて入力してください。")
        else:
            # --- 2. ドラフト生成処理 ---
            with st.spinner("⏳ Lean Canvas ドラフトを生成中...🤖"): # 処理中アニメーション
                # LLMへの入力情報を整形
                input_summary = "### 提供された情報:\n"
                for key, value in st.session_state.user_inputs.items():
                    input_summary += f"- {key}: {value if value else '(未入力)'}\n"

                # ドラフト生成用プロンプト
                canvas_prompt = f"""
                あなたは経験豊富なインキュベーターです。
                以下の提供された情報に基づいて、新規事業のアイデアを整理するため、Lean Canvasのドラフトを作成してください。
                {input_summary}
                ### 指示:
                1. 上記の「提供された情報」を最大限活用し、Lean Canvasの各項目を埋めてください。
                2. 特に「課題」「顧客セグメント」「ソリューション」「独自の価値提案」「圧倒的優位性」は、提供された情報を反映し、具体的に記述してください。
                3. 他の項目（チャネル、収益の流れ、コスト構造、主要指標）についても、提供された情報から推測できる範囲でアイデアを記述してください。不明瞭な点は「要検討」としても構いません。
                4. 全体として一貫性のあるドラフトになるようにしてください。
                5. 出力はMarkdown形式で見やすく記述してください。各項目は見出し（例: `**課題:**`）としてください。

                ### Lean Canvas ドラフト案:
                """
                try:
                    # API呼び出し
                    canvas_response = model.generate_content(canvas_prompt, safety_settings=safety_settings)
                    # 結果をSession Stateに保存
                    st.session_state.canvas_draft = canvas_response.text
                except Exception as e:
                    st.error(f"❌ Lean Canvasドラフト生成中にエラーが発生しました: {e}")

# --- 3. ドラフト表示 ---
if st.session_state.canvas_draft:
    st.header("2. 生成された Lean Canvas ドラフト")
    st.markdown(st.session_state.canvas_draft) # Markdownとして表示
    st.info("📝 これはAIによって生成されたドラフトです。内容を確認し、自身の考えと照らし合わせてください。")

    # --- 4. フィードバック取得 ---
    st.header("3. AIからのフィードバック")
    st.markdown("生成されたドラフトに対して、AI（VC役）からのフィードバックを取得します。")
    if st.button("🔍 フィードバックを取得する"):
        # 以前のフィードバックと改訂版をクリア
        st.session_state.feedback = ""
        st.session_state.revised_canvas = ""
        with st.spinner("⏳ フィードバックを生成中...🧐"):
            # フィードバック用プロンプト
            feedback_prompt = f"""
            あなたは経験豊富なベンチャーキャピタリスト（VC）です。
            以下のLean Canvasのドラフトを厳しくレビューし、建設的なフィードバックを提供してください。

            ### レビュー対象のLean Canvas ドラフト:
            ```markdown
            {st.session_state.canvas_draft}
            ```

            ### フィードバックの観点:
            1.  **強み (Strengths):** このプランの良い点、可能性を感じる点はどこですか？
            2.  **弱み/懸念点 (Weaknesses/Concerns):** 不明瞭な点、矛盾している点、リスクが高いと考えられる点、具体性が不足している点はどこですか？ 仮説が甘い部分はありますか？
            3.  **不足している視点 (Missing Perspectives):** 考慮されていない重要な要素（顧客ニーズの深掘り、競合分析、市場規模、市場トレンド、規制、仮説検証の方法など）はありますか？ 技術オリエンテッドになりすぎていませんか？
            4.  **次に行うべきこと/問いかけ (Next Steps/Questions):** この事業アイデアを成功に近づけるために、作成者は次に何を考え、何を検証すべきですか？ 具体的な問いかけを最低3つ記述してください。

            フィードバックは、単なる感想ではなく、具体的で、示唆に富み、行動につながるように記述してください。厳しい視点も歓迎します。出力はMarkdown形式でお願いします。
            """
            try:
                # API呼び出し
                feedback_response = model.generate_content(feedback_prompt, safety_settings=safety_settings)
                # 結果をSession Stateに保存
                st.session_state.feedback = feedback_response.text
            except Exception as e:
                st.error(f"❌ フィードバック生成中にエラーが発生しました: {e}")

# --- 5. フィードバック表示 ---
if st.session_state.feedback:
     st.markdown("---") # 区切り線
     st.subheader("AIからのフィードバック:")
     st.markdown(st.session_state.feedback) # Markdownとして表示

     # --- 6. 改訂版生成 ---
     st.header("4. フィードバックを基にした改訂")
     st.markdown("AIからのフィードバックを参考に、Lean Canvasの改訂版を生成します。")
     if st.button("✍️ フィードバックを基に改訂版を生成する"):
         st.session_state.revised_canvas = "" # 以前の改訂版をクリア
         with st.spinner("⏳ 改訂版 Lean Canvas を生成中..."):
             # 改訂用プロンプト
             revision_prompt = f"""
             あなたは経験豊富なビジネスストラテジストです。
             以下の「元のLean Canvasドラフト」と、それに対する「フィードバック」を読み、フィードバックの内容を反映させて**改訂版のLean Canvas**を作成してください。

             ### 元のLean Canvas ドラフト:
             ```markdown
             {st.session_state.canvas_draft}
             ```

             ### フィードバック:
             ```markdown
             {st.session_state.feedback}
             ```

             ### 改訂指示:
             1.  フィードバックで指摘された弱点や懸念点に対処するように、元のドラフトの内容を修正・追記してください。
             2.  フィードバックで提案された「次に行うべきこと」や「問いかけ」に対する答えを、可能な範囲でキャンバスの項目に反映させてください。（例：仮説検証の方法を[主要指標]に加える、リスクを[コスト構造]や[課題]で考慮するなど）
             3.  元のドラフトの強みは維持・強化するようにしてください。
             4.  改訂後のLean Canvas全体を出力してください。元のドラフトの形式を踏襲し、Markdown形式で見やすく記述してください。各項目は見出し（例：`**課題:**`）としてください。

             ### 改訂版 Lean Canvas:
             """
             try:
                 # API呼び出し
                 revision_response = model.generate_content(revision_prompt, safety_settings=safety_settings)
                 # 結果をSession Stateに保存
                 st.session_state.revised_canvas = revision_response.text
             except Exception as e:
                 st.error(f"❌ 改訂版Lean Canvas生成中にエラーが発生しました: {e}")

# --- 7. 改訂版表示 ---
if st.session_state.revised_canvas:
    st.markdown("---")
    st.header("5. 改訂版 Lean Canvas")
    st.markdown(st.session_state.revised_canvas)
    st.success("✅ 改訂版が生成されました！この内容を基に、さらに具体的なアクションプランを検討しましょう。")

# --- フッター（任意） ---
st.markdown("---")
st.caption("Powered by Google Gemini & Streamlit")