@echo off
REM 切换代码页到 UTF-8
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ========================================================
REM 语言选择菜单 (Menu in English for compatibility)
REM ========================================================
:LANGUAGE_SELECT
cls
echo ========================================================
echo             Parakeet-TDT-GUI Launcher
echo ========================================================
echo Please select your language:
echo.
echo 1. Chinese (简体中文)
echo 2. English
echo 3. Japanese (日本語)
echo 4. Korean (한국어)
echo ========================================================
set /p lang_choice="Input Option [1-4]: "

if "%lang_choice%"=="1" goto LANG_CN
if "%lang_choice%"=="2" goto LANG_EN
if "%lang_choice%"=="3" goto LANG_JA
if "%lang_choice%"=="4" goto LANG_KO
goto LANGUAGE_SELECT

REM ========================================================
REM 语言变量定义 (Define Variables)
REM ========================================================

:LANG_CN
set "MSG_TRY_ACTIVATE=正在尝试激活虚拟环境 .venv..."
set "MSG_ERR_NO_VENV=错误：虚拟环境 .venv 未找到或不完整。"
set "MSG_ERR_FIX=请先运行 'install_dependencies.bat' 来创建和配置环境。"
set "MSG_ACT_SUCCESS=虚拟环境已激活。"
set "MSG_STARTING=正在启动应用程序 (main.py)..."
set "MSG_TIP_ERR=如果程序没有立即显示界面，请检查命令行输出是否有错误信息。"
set "MSG_TIP_URL=Gradio 通常会打印本地 URL (例如 http://127.0.0.1:7860)。"
set "MSG_TIP_BROWSER=请在浏览器中访问该地址。"
set "MSG_TIP_TIME=初次启动耗时可能较长，请耐心等待。"
set "MSG_CLOSED=应用程序已关闭或已结束。"
goto MAIN_LOGIC

:LANG_EN
set "MSG_TRY_ACTIVATE=Attempting to activate virtual environment .venv..."
set "MSG_ERR_NO_VENV=Error: Virtual environment .venv not found or incomplete."
set "MSG_ERR_FIX=Please run 'install_dependencies.bat' first."
set "MSG_ACT_SUCCESS=Virtual environment activated."
set "MSG_STARTING=Starting application (main.py)..."
set "MSG_TIP_ERR=If the UI does not appear, check this console for errors."
set "MSG_TIP_URL=Gradio usually runs at http://127.0.0.1:7860."
set "MSG_TIP_BROWSER=Please open this URL in your browser."
set "MSG_TIP_TIME=First launch may take a long time. Please wait."
set "MSG_CLOSED=Application closed."
goto MAIN_LOGIC

:LANG_JA
set "MSG_TRY_ACTIVATE=仮想環境 .venv をアクティブ化しています..."
set "MSG_ERR_NO_VENV=エラー：仮想環境 .venv が見つかりません。"
set "MSG_ERR_FIX=先に 'install_dependencies.bat' を実行してください。"
set "MSG_ACT_SUCCESS=仮想環境がアクティブ化されました。"
set "MSG_STARTING=アプリケーション (main.py) を起動しています..."
set "MSG_TIP_ERR=画面が表示されない場合は、エラーメッセージを確認してください。"
set "MSG_TIP_URL=Gradio URL (例: http://127.0.0.1:7860) を確認してください。"
set "MSG_TIP_BROWSER=ブラウザでそのURLを開いてください。"
set "MSG_TIP_TIME=初回起動には時間がかかる場合があります。"
set "MSG_CLOSED=アプリケーションが終了しました。"
goto MAIN_LOGIC

:LANG_KO
set "MSG_TRY_ACTIVATE=가상 환경 .venv 활성화 시도 중..."
set "MSG_ERR_NO_VENV=오류: 가상 환경 .venv를 찾을 수 없습니다."
set "MSG_ERR_FIX='install_dependencies.bat'를 먼저 실행하십시오."
set "MSG_ACT_SUCCESS=가상 환경이 활성화되었습니다."
set "MSG_STARTING=애플리케이션 (main.py) 시작 중..."
set "MSG_TIP_ERR=UI가 나타나지 않으면 콘솔 오류를 확인하십시오."
set "MSG_TIP_URL=Gradio URL(예: http://127.0.0.1:7860)을 확인하십시오."
set "MSG_TIP_BROWSER=브라우저에서 해당 주소를 여십시오."
set "MSG_TIP_TIME=처음 시작하는 데 시간이 걸릴 수 있습니다."
set "MSG_CLOSED=애플리케이션이 종료되었습니다."
goto MAIN_LOGIC

REM ========================================================
REM 主逻辑 (Main Logic)
REM ========================================================

:MAIN_LOGIC
echo.
echo %MSG_TRY_ACTIVATE%

REM 检查虚拟环境是否存在
if not exist .\.venv\Scripts\activate.bat (
    echo.
    echo %MSG_ERR_NO_VENV%
    echo %MSG_ERR_FIX%
    pause
    exit /b
)

REM 激活环境
call .\.venv\Scripts\activate.bat
echo %MSG_ACT_SUCCESS%

echo.
echo ========================================================
echo %MSG_STARTING%
echo ========================================================
echo %MSG_TIP_ERR%
echo %MSG_TIP_URL%
echo %MSG_TIP_BROWSER%
echo %MSG_TIP_TIME%
echo ========================================================
echo.

REM 设置 UTF-8 运行环境
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM 启动 Python 主程序
python main.py

echo.
echo %MSG_CLOSED%
pause
exit /b