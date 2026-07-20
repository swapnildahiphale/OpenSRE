def test_fastembed_returns_fixed_dim_vector():
    from memory.embeddings import FastEmbedEmbedder

    emb = FastEmbedEmbedder()
    v = emb.embed("payment-service connection pool exhausted")
    assert isinstance(v, list)
    assert len(v) == emb.dimensions == 384
    assert all(isinstance(x, float) for x in v)


def test_default_embedder_is_singleton():
    from memory.embeddings import get_default_embedder

    assert get_default_embedder() is get_default_embedder()
