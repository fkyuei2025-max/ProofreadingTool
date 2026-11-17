import streamlit as st
from google import genai
from google.genai import types
import tempfile
import os

# ブラウザのタブ設定
st.set_page_config(
    page_title="AI PDF校正ツール",
    page_icon="📕",
    layout="centered"
)

# --- 🔒 簡易パスワード認証機能 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔒 PDF AI校正ツール")
        pwd = st.text_input("利用パスワードを入力してください", type="password")
        if st.button("ログイン"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("パスワードが間違っています。")
        st.stop()

check_password()
# ---------------------------------

# タイトルと赤い「PDF」SVGアイコンの表示
st.markdown(
    """
    <h1 style="display: flex; align-items: center; gap: 12px;">
        <svg width="42" height="42" viewBox="0 0 24 24" fill="none" xmlns="http://w3.org">
            <path d="M6 2C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2H6Z" fill="#E53935"/>
            <path d="M14 2V8H20" fill="#FFCDD2"/>
            <text x="12" y="17.5" fill="white" font-size="6.5" font-weight="bold" font-family="sans-serif" text-anchor="middle">PDF</text>
        </svg>
        <span>AI PDF校正ツール</span>
    </h1>
    """,
    unsafe_allow_html=True
)
st.write("Google Geminiを用いてPDFの誤字・脱字・表記ゆれを校正するツールです。")

# ハイライト用のデザイン（CSS）
st.markdown(
    """
    <style>
    .issue-header {
        font-size: 1.15em;
        font-weight: bold;
        color: #1E1E1E;
        background-color: #F4F6F8;
        border-left: 5px solid #E53935;
        padding: 6px 12px;
        margin-top: 20px;
        margin-bottom: 10px;
        border-radius: 0 4px 4px 0;
    }
    del.diff-del {
        color: #E53935;
        background-color: #FFEBEE;
        text-decoration: line-through;
        font-weight: bold;
        padding: 1px 4px;
        border-radius: 3px;
    }
    u.diff-add {
        color: #D32F2F;
        background-color: #FFF8E1;
        text-decoration: underline;
        text-decoration-thickness: 2px;
        font-weight: bold;
        padding: 1px 4px;
        border-radius: 3px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# クラウドの安全な金庫（Secrets）からAPIキーを読み込む
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(timeout=600000)
)

uploaded_file = st.file_uploader("PDFファイルをドラッグ＆ドロップしてください", type=["pdf"])

if uploaded_file is not None:
    st.success(f"ファイル「{uploaded_file.name}」を読み込みました。")
    
    if st.button("校正を実行する", type="primary"):
        tmp_file_path = None
        pdf_file = None
        
        # 1. 進行状況バー（ここは処理中の案内だけを表示）
        status = st.status("AIがPDFを解析中...", expanded=True)
        
        try:
            status.write("⏳ PDFをGoogleの専用解析サーバーへ転送中...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            pdf_file = client.files.upload(file=tmp_file_path)
            
            status.write("🚀 解析を開始しました。下にリアルタイムで結果が表示されます...")
            
            prompt = """
            添付されたPDFファイルをすべて確認し、文章の「誤字脱字」および「表記ゆれ」の検出に特化した厳密な校正を行ってください。

            【重要：校正のルール】
            - 文章の言い回しや表現の推敲、リライト提案は**一切不要**です。
            - 著者の文体や表現は尊重し、客観的なミスと不統一のみを抽出してください。
            - PDFの仕様上、二重かぎ括弧『』や一重かぎ括弧「」が読み取り時に崩れることがあるため、括弧単体の文字化けやペアのズレは指摘から除外してください。
            - 指摘すべき箇所が全くない場合は「誤字脱字・表記ゆれは見つかりませんでした」とだけ回答してください。

            【重点チェック項目】
            1. 誤字・脱字（漢字の変換ミス、文字の抜け、重複した助詞など）
            2. 送り仮名の誤り
            3. 表記ゆれ（カタカナ語の長音有無、漢字とひらがなの混在、半角・全角の混在、固有名詞の不統一）

            【出力フォーマット・強調ルール】
            修正が必要な箇所のみ、以下の形式で出力してください。
            その際、元の文の間違っている文字は必ず <del class="diff-del">該当文字</del> で囲み、
            修正案の直した文字は必ず <u class="diff-add">修正文字</u> で囲んでください。

            <div class="issue-header">📍 指摘箇所 [ページ数]</div>
            - 種別：（誤字 / 脱字 / 送り仮名 / 表記ゆれ のいずれか）
            - 元の文：「ここに元の文を記載し、誤り部分だけ <del class="diff-del">誤字</del> で囲む」
            - 修正案：「ここに修正文を記載し、直した部分だけ <u class="diff-add">正字</u> で囲む」
            - 理由：（どの文字が誤っているか、または何ページ目の表記と統一すべきか）
            """
            
            response_stream = client.models.generate_content_stream(
                model='gemini-3.8-flash',
                contents=[pdf_file, prompt],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
            )
            
            # 2. 校正結果の表示エリア（statusボックスの外側に出すので絶対に閉じない）
            st.markdown("---")
            st.subheader("📝 校正結果")
            
            result_placeholder = st.empty()
            full_response = ""
            
            for chunk in response_stream:
                if chunk.text:
                    full_response += chunk.text
                    result_placeholder.markdown(full_response + "▌", unsafe_allow_html=True)
            
            # 確定表示
            result_placeholder.markdown(full_response, unsafe_allow_html=True)
            
            # 3. 上部のステータスを完了にしつつ、一番下にも完了メッセージを表示
            status.update(label="✅ 解析が完了しました", state="complete", expanded=False)
            st.success("🎉 すべての校正が完了しました！")
            
        except Exception as e:
            status.update(label="❌ 処理が中断されました", state="error", expanded=True)
            st.error(f"【エラー詳細】\n\n{e}")
            
        finally:
            if pdf_file:
                try:
                    client.files.delete(name=pdf_file.name)
                except Exception:
                    pass
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
