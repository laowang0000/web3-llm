from langchain_openai import OpenAIEmbeddings


def build_embeddings(model_name: str) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=model_name)
