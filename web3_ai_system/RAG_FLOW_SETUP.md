# RAG Flow Setup for Web3 LLM

## Recommended download path

将仓库克隆到本机后，RAG 流程核心路径为：

```text
D:\Coding\web3 llm\web3_ai_system
```

其中 RAG 引擎代码位于：

```text
D:\Coding\web3 llm\web3_ai_system\app\insight_engine
```

## 目录结构

RAG 相关目录：

- `app/insight_engine/`
  - `embeddings.py`
  - `loaders.py`
  - `splitter.py`
  - `vector_store.py`
  - `retriever.py`
  - `rag_pipeline.py`
  - `service.py`
  - `prompts.py`
- `data/insight_sources/`
  - `crypto_news/`
  - `on_chain_summaries/`
  - `market_reports/`

## 下载与准备步骤

1. 克隆仓库到本机：

```powershell
git clone https://github.com/laowang0000/web3-llm.git "D:\Coding\web3 llm"
```

2. 进入项目：

```powershell
cd "D:\Coding\web3 llm\web3_ai_system"
```

3. 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

4. 设置 OpenAI API Key：

```powershell
set OPENAI_API_KEY=your_openai_key_here
```

5. 确认数据目录存在并包含文本源：

```text
data/insight_sources/crypto_news/
`-- btc_etf_flow.txt

data/insight_sources/on_chain_summaries/
`-- eth_whale_activity.txt

data/insight_sources/market_reports/
`-- sol_liquidity_rotation.txt
```

6. 启动 Streamlit 应用：

```powershell
python run_streamlit.py
```

或者：

```powershell
streamlit run app/frontend/streamlit_app.py
```

7. 打开浏览器访问：

```text
http://localhost:8501
```

## 本地执行建议

如果你只想快速检查 RAG 流程是否准备完毕，可以运行 `setup_rag_flow.py`。它将：

- 检查 `data/insight_sources/` 目录结构
- 统计可加载文档数量
- 统计生成的文档块数量
- 显示 RAG 核心代码路径

```powershell
python setup_rag_flow.py
```

## 说明

本项目的 RAG 引擎使用：

- OpenAI Embeddings (`text-embedding-3-small`)
- Chroma 向量存储
- LangChain 文档加载与文本拆分
- `app/insight_engine/rag_pipeline.py` 进行检索与生成
