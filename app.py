import streamlit as st
from google import genai
from google.genai import types
from weasyprint import HTML
import tempfile
import os
from datetime import datetime

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

# 画面のデザイン（CSS）を共通変数として定義（画面表示とPDF出力の両方で同じ見た目にするため）
COMMON_CSS = """
    body {
        font-family: "Noto Sans CJK JP", "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif;
        color: #1E1E1E;
        font-size: 10.5pt;
    }
    .report-title {
        font-size: 16pt;
        font-weight: bold;
        border-bottom: 2px solid #E53935;
        padding-bottom: 6px;
        margin-bottom: 16px;
    }
    .issue-card {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        margin-top: 16px;
        margin-bottom: 16px;
        background-color: #FFFFFF;
        page-break-inside: avoid; /* PDF印刷時にカードの途中で改ページされるのを防ぐ */
        overflow: hidden;
    }
    .issue-header {
        font-size: 1.05em;
        font-weight: bold;
        color: #1E1E1E;
        background-color: #F1F3F5;
        border-left: 5px solid #E53935;
        padding: 7px 12px;
        border-bottom: 1px solid #E0E0E0;
    }
    .box-before {
        background-color: #FFF8F8;
        padding: 9px 12px;
        border-bottom: 1px dashed #FFCDD2;
        line-height: 1.6;
    }
    .box-after {
        background-color: #F4FBF7;
        padding: 9px 12px;
        border-bottom: 1px solid #E0E0E0;
        line-height: 1.6;
    }
    .label-before {
        display: inline-block;
        background-color: #E53935;
        color: white;
        font-size: 0.78em;
        font-weight: bold;
        padding: 2px 7px;
        border-radius: 4px;
        margin-right: 8px;
    }
    .label-after {
        display: inline-block;
        background-color: #2E7D32;
        color: white;
        font-size: 0.78em;
        font-weight: bold;
        padding: 2px 7px;
        border-radius: 4px;
        margin-right: 8px;
    }
    del.diff-del {
        color: #D32F2F;
        background-color: #FFCDD2;
        text-decoration: line-through;
        font-weight: bold;
        padding: 1px 4px;
        border-radius: 3px;
    }
    u.diff-add {
        color: #1B5E20;
        background-color: #C8E6C9;
        text-decoration: underline;
        text-decoration-thickness: 2px;
        font-weight: bold;
        padding: 1px 4px;
        border-radius: 3px;
    }
    .issue-meta {
        background-color: #FAFAFA;
        padding: 9px 12px;
        font-size: 0.9em;
        color: #424242;
        line-height: 1.5;
    }
    .complete-banner {
        background: linear-gradient(135deg, #2E7D32 0%, #43A047 100%);
        color: white;
        padding: 18px 24px;
        border-radius: 8px;
        text-align: center;
        font-size: 1.25em;
        font-weight: bold;
        margin-top: 30px;
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(46, 125, 50, 0.25);
        letter-spacing: 0.05em;
    }
"""

# 画面デザインのそのままを維持してPDFを生成する関数
def create_result_pdf(result_html: str, original_filename: str) -> bytes:
    full_html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 15mm;
            }}
            {COMMON_CSS}
        </style>
    </head>
    <body>
        <div class="report-title">【AI校正レポート】 {original_filename}</div>
        {result_html}
    </body>
    </html>
    """
    return HTML(string=full_html).write_pdf()

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

# --- タイトル下の箇条書き注釈 ---
st.markdown(
    """
    <div style="background-color: #F8F9FA; border-left: 4px solid #90A4AE; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px; font-size: 0.9em; color: #37474F;">
        <strong>【このツールについて】</strong>
        <ul style="margin-top: 6px; margin-bottom: 0; padding-left: 20px;">
            <li>アップロードされたPDFは校正完了後にサーバーから即座に削除されます。</li>
            <li>できるだけ軽いデータをアップロードしてください。（ファイルサイズによってクレジットを消費します。目安：1MB＝0.5円）</li>
        </ul>
        <strong>【校正についての注意点】</strong>
        <ul style="margin-top: 6px; margin-bottom: 0; padding-left: 20px;">
            <li>あくまで誤字・脱字等の簡単な確認ができる程度です。また、校正結果が必ずしも正しいとは限りません。</li>
            <li>ページ数や文字数が多いとAIの注意力が分散され詳細な結果が出力されにくくなります。</li>
            <li>名前の表記ゆれを確認したい場合は、必要なページだけ抽出してアップしたほうが正確な結果が出ます。</li>
        </ul>
    </div>
    """,
    unsafe_allow_html=True
)
# ---------------------------------

# 共通CSSを画面に適用
st.markdown(f"<style>{COMMON_CSS}</style>", unsafe_allow_html=True)

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
        
        status = st.status("AIがPDFを解析中...", expanded=True)
        
        try:
            status.write("⏳ PDFをGoogleの専用解析サーバーへ転送中...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            pdf_file = client.files.upload(file=tmp_file_path)
            
            status.write("🚀 解析を開始しました。下にリアルタイムで結果が表示されます...")
            
            current_year = datetime.now().year
            
            prompt = f"""
            添付されたPDFファイルをすべて確認し、文章の「誤字脱字」および「表記ゆれ」の検出に特化した厳密な校正を行ってください。
            所要時間の短縮よりも厳密さを重視してください。

            【重要：校正のルール】
            - 文章の言い回しや表現の推敲、リライト提案は**一切不要**です。
            - 著者の文体や表現は尊重し、客観的なミスと不統一のみを抽出してください。
            - PDFの仕様上、二重かぎ括弧『』や一重かぎ括弧「」が読み取り時に崩れることがあるため、括弧単体の文字化けやペアのズレは指摘から除外してください。
            - 指摘すべき箇所が全くない場合は「誤字脱字・表記ゆれは見つかりませんでした」とだけ回答してください。

            【重点チェック項目】
            1. 誤字・脱字（漢字の変換ミス、文字の抜け、重複した助詞など）
            2. 送り仮名の誤り
            3. 表記ゆれ（カタカナ語の長音有無、漢字とひらがなの混在、半角・全角の混在、固有名詞の不統一）
            4. 日時と曜日の整合性（令和・西暦の表記がなく前後からも判断できない場合は現在の年である{current_year}年を基準にする。その場合は理由欄に「{current_year}年〇月〇日の場合、〇曜日が正しい」と表記）

            【出力フォーマット・HTML構造ルール】
            修正が必要な箇所ごとに、**必ず以下のHTMLブロック構造そのまま**で出力してください。余計なマークダウン記号（```html など）は絶対に出力しないでください。
            その際、元の文の間違っている文字は必ず <del class="diff-del">該当文字</del> で囲み、
            修正案の直した文字は必ず <u class="diff-add">修正文字</u> で囲んでください。

            <div class="issue-card">
              <div class="issue-header">■ 指摘箇所 [ページ数]</div>
              <div class="box-before"><span class="label-before">元の文</span>ここに元の文を記載し、誤り部分だけ <del class="diff-del">誤字</del> で囲む</div>
              <div class="box-after"><span class="label-after">修正案</span>ここに修正文を記載し、直した部分だけ <u class="diff-add">正字</u> で囲む</div>
              <div class="issue-meta">
                <strong>・種別：</strong>（誤字 / 脱字 / 送り仮名 / 表記ゆれ / 日付・曜日不整合 のいずれか）<br>
                <strong>・理由：</strong>（どの文字が誤っているか、または何ページ目の表記と統一すべきか）
              </div>
            </div>
            """
            
            response_stream = client.models.generate_content_stream(
                model='gemini-3.8-flash',
                contents=[pdf_file, prompt],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
            )
            
            st.markdown("---")
            st.subheader("📝 校正結果")
            
            result_placeholder = st.empty()
            full_response = ""
            
            for chunk in response_stream:
                if chunk.text:
                    full_response += chunk.text
                    clean_stream = full_response.replace("```html", "").replace("```", "")
                    result_placeholder.markdown(clean_stream + "▌", unsafe_allow_html=True)
            
            final_clean_response = full_response.replace("```html", "").replace("```", "")
            result_placeholder.markdown(final_clean_response, unsafe_allow_html=True)
            status.update(label="✅ 解析が完了しました", state="complete", expanded=False)
            
            st.markdown(
                '<div class="complete-banner">🎉 すべての校正が完了しました！</div>',
                unsafe_allow_html=True
            )
            
            pdf_bytes = create_result_pdf(final_clean_response, uploaded_file.name)
            base_name = os.path.splitext(uploaded_file.name)[0]
            
            st.download_button(
                label="📥 校正結果をPDFファイルでダウンロードする",
                data=pdf_bytes,
                file_name=f"校正結果_{base_name}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
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
