_ARXIV_NS = "{http://arxiv.org/OAI/arXiv/}"
_BASE_URL = "https://oaipmh.arxiv.org/oai"  # ArXiv migrated OAI-PMH here
_FALLBACK_URLS = [
    "https://oaipmh.arxiv.org/oai",   # Current ArXiv OAI-PMH host
    "http://export.arxiv.org/oai2",   # Legacy host (now 301-redirects to the above)
]
_OAI_NS = "{http://www.openarchives.org/OAI/2.0/}"
_MIN_INTERVAL = 3.0  # ≤ 1 request / 3 s (arXiv legacy policy)

# Task Types
TASK_TYPE_NEWSLETTER = "newsletter"
TASK_TYPE_PODCAST = "podcast"
TASK_TYPE_VISUALIZER = "visualizer"
TASK_TYPE_CUSTOM_NEWSLETTER_RUN = "custom_newsletter_run"
TASK_TYPE_DATABASE_EXPORT = "database_export"
TASK_TYPE_DATABASE_IMPORT = "database_import"
TASK_TYPE_RESEARCH_AGENT = "research_agent"

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