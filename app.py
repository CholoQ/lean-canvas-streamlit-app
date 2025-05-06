# --- 修正後の正しいコード ---
import streamlit as st # stをインポート
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import sys
# Streamlitのエラークラスをインポート (存在しない場合を考慮)
try:
    from streamlit.errors import StreamlitAPIException
except ImportError:
    StreamlitAPIException = Exception

api_key = None # api_key変数を初期化

try:
    # まず Streamlit secrets を試す (デプロイ環境向け)
    # ★★★ 引数に正しい名前 "GEMINI_API_KEY" を指定 ★★★
    api_key = st.secrets.get("GEMINI_API_KEY")
    if api_key is None: # .get はキーがない場合 None を返す (エラーは出さない場合がある)
        raise StreamlitAPIException("SecretsにGEMINI_API_KEYが見つかりません") # 強制的にexceptに移行
    if not api_key:
         st.error("⚠️ GEMINI_API_KEY が Streamlit Secrets にありますが、値が空です。")
         st.stop()

except StreamlitAPIException:
    # Streamlit secrets が見つからない場合 (ローカル環境など)
    # ★★★ 引数に正しい名前 "GEMINI_API_KEY" を指定 ★★★
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # 環境変数にも見つからない場合
        st.error("⚠️ APIキーが設定されていません。Streamlit Secrets または環境変数に `GEMINI_API_KEY` を設定してください。")
        st.stop()

except Exception as e:
    # その他の予期せぬエラー
    st.error(f"❌ APIキーの読み込み中に予期せぬエラーが発生しました: {e}")
    st.stop()


# APIキーが正常に取得できた場合のみ、genaiを設定
if api_key:
    try:
        genai.configure(api_key=api_key)
        model_name = 'gemini-1.5-flash-latest'
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        st.error(f"❌ Geminiモデルの初期化中にエラーが発生しました: {e}")
        st.stop()
else:
    st.error("❌ APIキーの取得に失敗したため、初期化できませんでした。")
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

# --- 1. コア情報入力フォーム ---
st.header("1. アイデアのコア情報を入力")
st.markdown("以下の項目について、具体的な情報を入力してください。")

with st.form("lean_canvas_input_form"):
    questions = {
        "ターゲット顧客": "[顧客セグメント] あなたが最初に価値を届けたい具体的な顧客は誰ですか？",
        "顧客の課題": "[課題] その顧客が抱えている最も重要な課題は何ですか？",
        "提供する解決策": "[ソリューション] あなたの技術やアイデアは、その課題を具体的にどう解決しますか？",
        "競合": "[競合] 現時点で考えられる主な競合製品・サービス、または顧客が課題を解決している代替手段は何ですか？",
        "コア技術": "[ソリューション/優位性] アイデアの中心となる技術やアプローチは何ですか？ (任意)",
        "既存比較と優位性": "[独自の価値提案/優位性] 既存の解決策や競合と比べて、あなたのアイデアは何がどう優れていますか？",
        "市場情報": "[市場] ターゲット市場のおおよその規模や成長性について、現時点で分かっていることがあれば教えてください。(任意)"
    }
    # フォーム内にテキストエリアを配置
    for key, question in questions.items():
        st.session_state.user_inputs[key] = st.text_area(
            question,
            value=st.session_state.user_inputs.get(key, ""),
            height=100,
            key=f"input_{key}"
        )

    submitted = st.form_submit_button("🚀 Lean Canvas ドラフト生成")

    # --- ボタンが押された後の処理 ---
    if submitted:
        # 以前の結果をクリア
        st.session_state.canvas_draft = ""
        st.session_state.feedback = ""
        st.session_state.revised_canvas = ""

        # デバッグ用に追加
        st.write("DEBUG: Submit button clicked.")

        # 必須項目チェック
        required_keys = ["ターゲット顧客", "顧客の課題", "提供する解決策", "競合", "既存比較と優位性"]
        all_required_filled = all(st.session_state.user_inputs.get(key) for key in required_keys)

        # デバッグ用に追加
        st.write(f"DEBUG: Required fields check passed: {all_required_filled}")

        if not all_required_filled:
             st.warning("⚠️ 必須項目（ターゲット顧客、顧客の課題、提供する解決策、競合、既存比較と優位性）をすべて入力してください。")
        else:
            # 必須項目が満たされていればAPI呼び出しへ
            with st.spinner("⏳ Lean Canvas ドラフトを生成中...🤖"):
                # input_summary の作成
                input_summary = "### 提供された情報:\n"
                for key, value in st.session_state.user_inputs.items():
                    input_summary += f"- {key}: {value if value else '(未入力)'}\n"

                # デバッグ用に input_summary を表示
                st.text_area("DEBUG Input Summary:", input_summary, height=200)

                # プロンプトの定義 (元に戻したシンプルなバージョン)
                canvas_prompt = f"""
                あなたは経験豊富なインキュベーターです。
                以下の提供された情報に基づいて、新規事業のアイデアを整理するため、Lean Canvasのドラフトを作成してください。
                {input_summary}
                ### 指示:
                1. 上記の「提供された情報」を最大限活用し、Lean Canvasの各項目を埋めてください。
                2. 特に「課題」「顧客セグメント」「ソリューション」「独自の価値提案」「圧倒的優位性」は具体的に記述してください。
                3. 他の項目も推測できる範囲で記述してください。
                4. 出力はMarkdown形式で見やすく記述してください。各項目は見出し（例：`**課題:**`）としてください。

                ### Lean Canvas ドラフト案:
                """

                # デバッグ用に追加
                st.write("DEBUG: Attempting to call Gemini API for canvas...")
                # st.text_area("DEBUG Final Prompt Sent:", canvas_prompt, height=300) # 必要ならコメントアウト解除

                # --- API呼び出しとデバッグ情報取得 (ここを修正) ---
                try: # 外側のtry: API呼び出し全体を囲む
                    canvas_response = model.generate_content(canvas_prompt, safety_settings=safety_settings)

                    # デバッグ用に追加
                    st.write("DEBUG: API call successful. Processing response...")

                    st.session_state.canvas_draft = canvas_response.text

                    # ★デバッグ用に追加 (API応答詳細)
                    try: # 内側のtry: デバッグ情報取得部分を囲む
                        finish_reason = "不明"
                        prompt_feedback_info = "N/A"
                        safety_ratings_info = "N/A"
                        # candidates属性とリストの存在を確認
                        if hasattr(canvas_response, 'candidates') and canvas_response.candidates:
                             candidate = canvas_response.candidates[0] # 最初の候補を取得
                             # 各属性の存在を確認してからアクセス
                             if hasattr(candidate, 'finish_reason'):
                                 finish_reason = candidate.finish_reason
                             if hasattr(candidate, 'safety_ratings'):
                                 safety_ratings_info = candidate.safety_ratings
                        # prompt_feedback属性の存在を確認してからアクセス
                        if hasattr(canvas_response, 'prompt_feedback'):
                             prompt_feedback_info = canvas_response.prompt_feedback

                        # Streamlit画面にデバッグ情報を表示
                        st.subheader("DEBUG: API Response Details")
                        st.write(f"- Finish Reason: `{finish_reason}`")
                        st.write(f"- Prompt Feedback: `{prompt_feedback_info}`")
                        st.write(f"- Safety Ratings: `{safety_ratings_info}`")

                    except Exception as debug_e: # 内側のexcept
                        st.warning(f"Could not retrieve all debug info from response: {debug_e}")

                    # デバッグ用に追加 (Session State更新確認)
                    st.write("DEBUG: canvas_draft session state updated.")

                except Exception as e: # 外側のexcept: API呼び出し自体のエラーを捕捉
                    # デバッグ用にエラーをUIにも表示
                    st.error(f"❌ Lean Canvasドラフト生成中にエラーが発生しました(DEBUG): {e}")
                    # ターミナルにもスタックトレースが表示されるはず

# --- 3. ドラフト表示 ---
# (変更なし)
if st.session_state.canvas_draft:
    st.header("2. 生成された Lean Canvas ドラフト")
    st.markdown(st.session_state.canvas_draft)
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

# --- 8. 他のフレームワークでの分析 ---
if st.session_state.revised_canvas or st.session_state.canvas_draft: # ドラフトか改訂版があれば分析可能
    st.header("6. 追加分析フレームワーク")
    st.markdown("Lean Canvasの内容を基に、他のビジネスフレームワークで分析を深めます。")

    # 分析に使用するLean Canvasのテキストを決定（改訂版があれば優先）
    canvas_for_analysis = st.session_state.revised_canvas if st.session_state.revised_canvas else st.session_state.canvas_draft

    # --- ↓↓↓ 選択肢リストを修正 ↓↓↓ ---
    analysis_options = [
        "選択してください...",
        "バリュープロポジションキャンバス",
        "4P分析", # 追加
        "3C分析", # 追加
        "SWOT分析"  # SWOTも例として追加（不要なら削除）
        ]
    # --- ↑↑↑ 選択肢リストを修正 ↑↑↑ ---
    selected_analysis = st.selectbox("実行したい分析を選択してください:", analysis_options, key="analysis_selectbox")

    # --- 分析実行ボタンと条件分岐 ---
    # selected_analysis が "選択してください..." でない場合のみボタンを表示
    if selected_analysis != "選択してください...":
        if st.button(f"📊 {selected_analysis} を実行する", key=f"run_{selected_analysis}_button"):
            # Session Stateキーを生成
            analysis_key = f'analysis_{selected_analysis}'
            # 既存の分析結果があればクリア
            if analysis_key in st.session_state:
                del st.session_state[analysis_key]

            with st.spinner(f"⏳ {selected_analysis} を生成中..."):
                analysis_prompt = "" # プロンプトを初期化

                # --- ↓↓↓ elif ブロックを追加 ↓↓↓ ---
                if selected_analysis == "バリュープロポジションキャンバス":
                    analysis_prompt = f"""
                    あなたは顧客理解と価値提案の専門家です。
                    以下のLean Canvasの情報（特に顧客セグメント、課題、独自の価値提案、ソリューション）を最重要視し、バリュープロポジションキャンバスの6つの要素を具体的に記述してください。
                    ### Lean Canvas 情報:
                    ```markdown
                    {canvas_for_analysis}
                    ```
                    ### バリュープロポジションキャンバス案:
                    ...(VPC用プロンプト詳細)...
                    結果はMarkdown形式で見出しを付けて分かりやすく記述してください。
                    """
                elif selected_analysis == "4P分析": # ★4P分析の処理を追加
                    analysis_prompt = f"""
                    あなたは経験豊富なマーケティング戦略家です。
                    以下のLean Canvasの情報に基づき、この事業のマーケティングミックスについて4P分析（Product, Price, Place, Promotion）の観点から具体的な戦略案を提案してください。

                    ### Lean Canvas 情報:
                    ```markdown
                    {canvas_for_analysis}
                    ```

                    ### 4P分析案:
                    **Product (製品・サービス):** (顧客の課題を解決する具体的な製品・サービスの詳細、特徴、品質、デザイン、ブランドなどについて)
                    **Price (価格):** (価格設定戦略、価格帯、割引、支払い条件などについて)
                    **Place (流通・場所):** (顧客が製品・サービスにアクセスできる場所や方法、チャネル、物流などについて。Lean Canvasの[チャネル]も参考に)
                    **Promotion (販促):** (ターゲット顧客への認知度向上、関心喚起、購買意欲促進のための具体的な手法。広告、広報、SNS、イベントなどについて)

                    結果はMarkdown形式で見出しを付けて分かりやすく記述してください。
                    """
                elif selected_analysis == "3C分析": # ★3C分析の処理を追加
                    analysis_prompt = f"""
                    あなたは経験豊富な経営コンサルタントです。
                    以下のLean Canvasの情報、特に[顧客セグメント]、[課題]、[ソリューション]、[競合]、[圧倒的優位性]を参考に、この事業を取り巻く3C分析（Customer, Competitor, Company）を行ってください。

                    ### Lean Canvas 情報:
                    ```markdown
                    {canvas_for_analysis}
                    ```

                    ### 3C分析:
                    **Customer (市場・顧客):** (ターゲット顧客のニーズの深掘り、市場規模や成長性（もし情報があれば）、顧客の行動や意思決定プロセスについて分析してください)
                    **Competitor (競合):** (Lean Canvasの[競合]で挙げられた競合や代替手段について、それらの強み・弱みを分析し、自社と比較してください)
                    **Company (自社):** (自社の強み（特に[圧倒的優位性]）、弱み、利用可能なリソース（技術、人材、資金など）、経営課題について分析してください)

                    結果はMarkdown形式で見出しを付けて分かりやすく記述してください。競合と比較した上での自社の位置づけが明確になるようにしてください。
                    """
                elif selected_analysis == "SWOT分析": # ★SWOT分析の処理を追加 (例として)
                     analysis_prompt = f"""
                     あなたは経験豊富なビジネスアナリストです。
                     以下のLean Canvasの情報に基づき、この事業のSWOT分析（Strengths:強み, Weaknesses:弱み, Opportunities:機会, Threats:脅威）を行ってください。内部環境（強み・弱み）と外部環境（機会・脅威）を明確に区別してください。

                     ### Lean Canvas:
                     ```markdown
                     {canvas_for_analysis}
                     ```

                     ### SWOT分析:
                     **Strengths (強み):**
                     **Weaknesses (弱み):**
                     **Opportunities (機会):**
                     **Threats (脅威):**

                     結果はMarkdown形式で見出しを付けて分かりやすく記述してください。
                     """
                # --- ↑↑↑ elif ブロックを追加 ↑↑↑ ---

                # プロンプトが生成されていればAPI呼び出し実行
                if analysis_prompt:
                    try:
                        analysis_response = model.generate_content(analysis_prompt, safety_settings=safety_settings)
                        # 分析結果をSession Stateに保存
                        st.session_state[analysis_key] = analysis_response.text
                    except Exception as e:
                        st.error(f"❌ {selected_analysis} 生成中にエラーが発生しました: {e}")
                else:
                    st.warning("選択された分析に対応するプロンプトが定義されていません。")

    # --- 分析結果の表示 ---
    # ↓↓↓ 表示ループを修正 ↓↓↓
    st.markdown("---") # 区切り線
    st.subheader("分析結果:")
    analysis_displayed = False # 何か表示されたかどうかのフラグ
    for option in analysis_options[1:]: # "選択してください..." を除くリストでループ
        analysis_key = f'analysis_{option}'
        if analysis_key in st.session_state and st.session_state[analysis_key]:
            with st.expander(f"▼ {option} 結果", expanded=False): # エキスパンダーで表示
                 st.markdown(st.session_state[analysis_key])
                 analysis_displayed = True # 表示フラグを立てる

    if not analysis_displayed:
        st.caption("実行したい分析を選択してボタンを押してください。") # まだ何も表示されていない場合
    # --- ↑↑↑ 表示ループを修正 ↑↑↑ ---

# --- フッター（任意） ---
# st.markdown("---")
# st.caption("Powered by Google Gemini & Streamlit")