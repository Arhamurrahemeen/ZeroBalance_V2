"""Rahbar tests: retrieval accuracy on the 10 pre-tested queries (real Qdrant +
local embedder, no network) and the ask flow with a fake Groq client."""

import pytest

from app.rahbar import (
    SAMPLE_QUERIES,
    SAMPLE_QUERIES_EN,
    ask,
    ensure_indexed,
    load_corpus,
    retrieve,
    sample_query_pairs,
)

# each pre-tested query -> corpus doc id that must appear in top-3
EXPECTED = {
    SAMPLE_QUERIES[0]: 1,   # EOD balancing
    SAMPLE_QUERIES[1]: 2,   # denomination count
    SAMPLE_QUERIES[2]: 3,   # reporting threshold
    SAMPLE_QUERIES[3]: 4,   # shortage responsibility
    SAMPLE_QUERIES[4]: 5,   # duplicate posting
    SAMPLE_QUERIES[5]: 6,   # reversal approval
    SAMPLE_QUERIES[6]: 9,   # counterfeit notes
    SAMPLE_QUERIES[7]: 10,  # teller cash limit
    SAMPLE_QUERIES[8]: 11,  # vault transfer
    SAMPLE_QUERIES[9]: 8,   # wrong account
}


@pytest.fixture(scope="module", autouse=True)
def indexed() -> None:
    ensure_indexed()


def test_corpus_is_static_and_complete() -> None:
    docs = load_corpus()
    assert len(docs) == 16
    assert all("مصنوعی ڈیمو" in d["source"] for d in docs), "corpus must be marked synthetic"


@pytest.mark.parametrize("query", SAMPLE_QUERIES)
def test_pretested_query_retrieves_expected_snippet(query: str) -> None:
    hits = retrieve(query)
    assert len(hits) == 3
    assert EXPECTED[query] in [h["id"] for h in hits], (
        f"{query!r} retrieved {[(h['id'], h['title']) for h in hits]}"
    )


class _FakeGroq:
    class _Msg:
        content = "جواب: ماخذ: برانچ SOP"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.prompts_full: list[list[dict[str, str]]] = []

    @property
    def chat(self) -> "_FakeGroq":
        return self

    @property
    def completions(self) -> "_FakeGroq":
        return self

    def create(self, **kwargs: object) -> object:
        messages = kwargs["messages"]
        self.prompts.append(messages[-1]["content"])  # type: ignore[index]
        self.prompts_full.append(messages)  # type: ignore[arg-type]

        class R:
            class _Choice:
                message = _FakeGroq._Msg()

            choices = [_Choice()]

        return R()


def test_ask_grounds_answer_in_retrieved_context() -> None:
    fake = _FakeGroq()
    answer = ask(SAMPLE_QUERIES[4], client=fake)  # duplicate posting, defaults to lang="ur"
    assert answer.answer
    assert answer.lang == "ur"
    assert len(answer.sources) == 3
    prompt = fake.prompts[0]
    assert SAMPLE_QUERIES[4] in prompt
    dup_doc = next(d for d in load_corpus() if d["id"] == 5)
    assert dup_doc["text_ur"] in prompt, "retrieved snippet must be in the context"


def test_ask_lang_toggle_switches_system_prompt() -> None:
    fake = _FakeGroq()
    answer = ask(SAMPLE_QUERIES[0], lang="en", client=fake)
    assert answer.lang == "en"
    system_msg = fake.prompts_full[0][0]["content"]  # type: ignore[index]
    assert "plain English" in system_msg


def test_ask_rejects_unsupported_lang() -> None:
    with pytest.raises(ValueError):
        ask(SAMPLE_QUERIES[0], lang="fr", client=_FakeGroq())


def test_query_pairs_have_matching_english_labels() -> None:
    assert len(SAMPLE_QUERIES_EN) == len(SAMPLE_QUERIES) == 10
    pairs = sample_query_pairs()
    assert [p.ur for p in pairs] == SAMPLE_QUERIES
    assert [p.en for p in pairs] == SAMPLE_QUERIES_EN
    assert all(p.ur and p.en for p in pairs)
