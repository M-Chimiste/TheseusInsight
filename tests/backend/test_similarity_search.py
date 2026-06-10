"""Exercise the real pgvector similarity SQL with a fake embedder.

The endpoint lazily imports SentenceTransformerInference inside the handler
(api/routers/papers.py), so monkeypatching the attribute on
theseus_insight.inference takes effect at call time.
"""
import json

EMB_DIM = 768


class FakeEmbedder:
    """Stands in for SentenceTransformerInference; returns a vector near axis 0."""

    def __init__(self, model_name, remote_code=False):
        self.model_name = model_name

    def invoke(self, text):
        vec = [0.0] * EMB_DIM
        vec[0] = 0.9
        vec[1] = 0.1
        return vec


def test_similarity_search_orders_by_cosine(client, seeded_data, db, monkeypatch):
    # The handler reads the embedding model name from the stored config.
    db.execute(
        """
        INSERT INTO settings (key, value) VALUES ('orchestration', %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        (json.dumps({"embedding_model": {"model_name": "fake-model"}}),),
    )

    import theseus_insight.inference as inference

    monkeypatch.setattr(inference, "SentenceTransformerInference", FakeEmbedder)

    resp = client.post(
        "/api/papers/similarity-search",
        json={"query_text": "transformers", "limit": 10, "similarity_threshold": 0.05},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    titles = [p["title"] for p in body["results"]]
    # Query vector is ~axis 0: Alpha (axis 0) ranks above Beta (axis 1);
    # Gamma has no embedding and must not appear.
    assert titles == ["Alpha Paper", "Beta Paper"]
    assert body["total_results"] == 2
