# VoCap for Mac

从抖音视频链接提取口播文案的命令行工具。

把 App 分享文本、短链或网页长链交给它，会解析视频 ID、下载音频、在本地用 mlx-whisper 转成文字，并按 JSON / Markdown / SRT / 纯文本输出。语音识别在本机完成，音视频不会上传到第三方 ASR 服务。

当前仅支持：

- **macOS Apple Silicon**（M1 / M2 / M3 / M4 / M5）
- **抖音**链接：`v.douyin.com` 短链、`www.douyin.com/video/` 长链，以及含上述链接的分享文本

抖音网页接口会校验访客 cookie，并在连续请求时限流。日常提取需要从本机浏览器读取 cookie，批量时默认会间隔重试。

---

## 一、没有运行环境时：从零跑起来

按顺序做完本节后，本机就具备：系统工具、Python 虚拟环境、vocap 命令、ASR 引擎。首次真正提取时还会自动下载 Whisper 模型（约 1.6GB）。

### 1. 确认硬件与系统工具

| 依赖 | 用途 | 安装 |
|------|------|------|
| macOS Apple Silicon | mlx-whisper 只在 Apple 芯片上做 GPU 加速 | M 系列 Mac |
| Python 3.11+ | 运行 vocap | `brew install python`（当前 Homebrew 多为 3.14） |
| ffmpeg | 把下载的音频转成 16kHz 单声道 WAV | `brew install ffmpeg` |

```bash
python3 --version          # 需要 3.11 或更高
ffmpeg -version            # 能打印出版本即可
```

ffmpeg 是系统工具，不在 pip 包里，必须单独安装。

### 2. 拿到代码并创建虚拟环境

```bash
git clone <仓库地址>
cd vocap

python3 -m venv .venv
source .venv/bin/activate
```

激活成功后，提示符前会出现 `(.venv)`。之后每次新开终端都要先 `cd` 到项目目录再执行 `source .venv/bin/activate`。

若系统 `python3` 仍是 3.9（macOS 自带），请用 Homebrew 的解释器建环境：

```bash
/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate
```

虚拟环境必须和当前机器上的 Python 绑定。Homebrew 卸掉或升级了当初用来建 `.venv` 的版本后，会出现 `bad interpreter: python3.xx: no such file or directory`。这时删掉 `.venv`，用现在的 `python3` 重建即可。

### 3. 安装 vocap

国内安装 Python 包较慢时，可临时换清华源：

```bash
pip install -U pip
pip install -e ".[asr]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

| 安装命令 | 装什么 | 适用 |
|---------|--------|------|
| `pip install -e ".[asr]"` | httpx、yt-dlp、mlx-whisper | **日常提取（推荐）** |
| `pip install -e .` | 仅链接解析和下载 | 不跑识别 |
| `pip install -e ".[dev]"` | 核心依赖 + pytest、ruff | 跑测试（不含 ASR） |
| `pip install -e ".[dev,asr]"` | 开发 + 识别 | 改代码并本地提取 |

`-e` 是可编辑安装：改源码后不用重新 pip install。

`".[asr]"` 只装引擎代码，**不含**模型权重。第一次执行 `vocap` 时，若本地没有缓存，会从 Hugging Face 下载 `whisper-large-v3-turbo`（约 1.6GB），之后缓存在：

```
~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/
```

国内下载模型慢或失败时：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

可写入 `~/.zshrc`。磁盘不够时可改缓存位置：`export HF_HOME="/你的/路径"`。

### 4. 验证安装

```bash
source .venv/bin/activate
vocap --help
python3 -c "import mlx_whisper; print('mlx-whisper OK')"
```

能看到帮助信息，且 `mlx-whisper OK`，环境就算搭好。接下来按第二章做第一次提取。

### 5.（可选）开发者安装

```bash
source .venv/bin/activate
pip install -e ".[dev,asr]"

python -m pytest tests/ -v
ruff check src/ tests/
ruff format src/ tests/
```

ruff 装在虚拟环境里，需先激活，或直接调用 `.venv/bin/ruff`。

---

## 二、已有运行环境时：如何提取文案

默认你已经有可用的 `.venv`，并且装过 `".[asr]"`。每次开新终端：

```bash
cd /path/to/vocap
source .venv/bin/activate
```

### 1. 先准备抖音访客 cookie

抖音详情接口不再对匿名请求返回可用数据。vocap 通过 yt-dlp 读取**你本机浏览器**里的访客 cookie（不必登录账号）。

1. 用 Chrome（或 Safari）打开 [https://www.douyin.com](https://www.douyin.com)，停留几秒即可。
2. **完全退出浏览器**（macOS 上 cookie 库常被锁定，开着 Chrome 会读失败）。
3. 提取时加上 `--cookies-from-browser chrome`（Safari 则写 `safari`）。多配置可用 `chrome:Default` 或 `chrome:Profile 1`。

不要把 cookie 文件发到网上。`--cookies-from-browser` 与 `--cookies`（Netscape 格式的 `cookies.txt`）不能同时使用。

### 2. 常用命令

分享文本必须放在引号里。文本文件每行一条链接或分享文，`#` 开头的行视为注释。

```bash
# 单条短链，结果打到终端（JSON）
vocap "https://v.douyin.com/iRNBho5/" --cookies-from-browser chrome

# App 分享全文
vocap "7.46 复制打开抖音... https://v.douyin.com/X2rzKBxWv98/ ..." --cookies-from-browser chrome

# 网页长链，输出 Markdown
vocap "https://www.douyin.com/video/7380123456789" --cookies-from-browser chrome -f markdown

# 从文件批量提取并保存
vocap urls.txt --cookies-from-browser chrome -f markdown -o 文案.md

# 限流较狠时放慢间隔、增加重试
vocap urls.txt --cookies-from-browser chrome --sleep 5 --retries 5 -f markdown -o 文案.md

# 用已导出的 cookies.txt
vocap urls.txt --cookies ./cookies.txt -f txt -o 文案.txt

# 小模型试跑（更快、精度较低）
vocap "https://v.douyin.com/xxx" --cookies-from-browser chrome -m small
```

进度在终端标准错误输出；结果在标准输出，或由 `-o` 写入文件。批量时部分失败会继续处理其余链接，结束时退出码为 2。

### 3. 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `urls` | 抖音链接、分享文本、或包含链接的文本文件 | 必填 |
| `-f` / `--format` | `json` / `markdown`（`md`）/ `srt` / `txt` | `json` |
| `-o` / `--output` | 输出文件路径 | 打印到终端 |
| `-m` / `--model` | `tiny` / `base` / `small` / `medium` / `large-v3-turbo` / `large-v3` | `large-v3-turbo` |
| `--cookies-from-browser` | 从本机浏览器读 cookie。与 `--cookies` 互斥 | 无 |
| `--cookies` | Netscape `cookies.txt` 路径。与 `--cookies-from-browser` 互斥 | 无 |
| `--retries` | 遇到 `HTTP Error 403` 或 `Fresh cookies` 时的重试次数 | 3 |
| `--sleep` | 批量时两条之间的间隔（秒） | 3 |

### 4. 处理流程

```
分享文本或链接 → 抽出 URL → 短链重定向 → 视频 ID
                                         ↓
格式化输出 ← 文本清洗 ← 本地 ASR ← ffmpeg 转 WAV ← yt-dlp 下音频
```

短链会规范成 `https://www.douyin.com/video/{id}` 再交给 yt-dlp，避免跳到 `iesdouyin.com` 导致无法识别。

音频写在系统临时目录下以 `vocap_` 为前缀的文件夹中；识别结束或中途失败都会删除，不留在项目目录。

### 5. 常见问题

**`bad interpreter: ... python3.xx: no such file or directory`**  
虚拟环境指向的 Python 已被卸载。回到第一章第 2 步重建 `.venv` 并重新 `pip install -e ".[asr]"`。

**`Fresh cookies` 或 `HTTP Error 403`**  
先确认已打开过抖音网页并退出了浏览器。批量仍失败时加大 `--sleep`、`--retries`，或隔几分钟只重跑失败的那几条。报错里的「需要 cookie」有时是限流，并不代表浏览器里没有 cookie。

**第一次特别慢**  
正在下载 Whisper 模型。设置 `HF_ENDPOINT=https://hf-mirror.com` 后重试。

**Chrome 读 cookie 失败**  
退出 Chrome 全部窗口后再跑。可改用 Safari，或导出 `cookies.txt` 后加 `--cookies`。
