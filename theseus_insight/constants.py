_ARXIV_NS = "{http://arxiv.org/OAI/arXiv/}"
_BASE_URL = "https://export.arxiv.org/oai2"
_OAI_NS = "{http://www.openarchives.org/OAI/2.0/}"
_MIN_INTERVAL = 3.0  # ≤ 1 request / 3 s (arXiv legacy policy)
INTRO_TEXT = [
    "This fascinating study sheds light on...",
    "This research shows that...",
    "This paper explores...",
    "This research discusses...",
    "This paper investigates...",
    "This study presents...",
    "In this work, the authors examine...",
    "This article analyzes...",
    "This paper highlights...",
    "In this paper, the authors discuss...",
    "This investigation addresses...",
    "The research presented here explores...",
    "The authors provide insights into...",
    "This inquiry considers...",
    "This document discusses...",
    "Here, the study emphasizes...",
    "This work illuminates...",
    "This examination sheds light on...",
    "This contribution offers perspectives on...",
    "The paper provides an overview of...",
    "This scholarly work investigates...",
    "The following study presents findings on...",
    "This piece of research elaborates on...",
    "This article offers an analysis of...",
    "The authors explore...",
    "This study offers a comprehensive look at..."
]