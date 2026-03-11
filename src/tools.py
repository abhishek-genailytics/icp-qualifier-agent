import os
import requests
from langchain_core.tools import tool

# Industry enum values from the AI Ark API spec
# "SaaS" is not a valid enum — map user terms to valid ones
INDUSTRY_MAP = {
    "saas": "software development",
    "software": "software development",
    "tech": "technology, information and internet",
    "fintech": "financial services",
    "healthtech": "hospitals and health care",
    "edtech": "e-learning providers",
    "ecommerce": "retail",
    "ai": "technology, information and internet",
}

# Funding stage map: user-friendly → API enum
FUNDING_MAP = {
    "pre-seed": "PRE_SEED",
    "preseed": "PRE_SEED",
    "seed": "SEED",
    "series a": "SERIES_A",
    "series b": "SERIES_B",
    "series c": "SERIES_C",
    "series d": "SERIES_D",
    "series e": "SERIES_E",
    "venture": "VENTURE_ROUND",
    "angel": "ANGEL",
    "private equity": "PRIVATE_EQUITY",
    "growth": "SERIES_C",
}


def _normalize_industry(industry: str) -> str:
    """Map user-friendly industry terms to AI Ark enum values."""
    return INDUSTRY_MAP.get(industry.lower().strip(), industry.lower().strip())


def _normalize_funding(funding_stage: str) -> str | None:
    """Map user-friendly funding stage to AI Ark enum value."""
    return FUNDING_MAP.get(funding_stage.lower().strip())


@tool
def search_companies(
    industry: str = "",
    location: str = "",
    min_employees: int = 0,
    max_employees: int = 0,
    funding_stage: str = "",
    tech_stack: str = "",
    keywords: str = "",
    page: int = 0,
    size: int = 10,
) -> str:
    """
    Search for companies matching an Ideal Customer Profile (ICP) using the AI Ark Company Search API.
    Use this tool when the user wants to find target companies based on filters like industry,
    location, employee headcount range, funding stage, or technologies they use.

    Args:
        industry: Industry vertical (e.g. "SaaS", "FinTech", "software development")
        location: City, region, or country (e.g. "Bangalore", "India", "United States")
        min_employees: Minimum number of employees (0 = no lower bound)
        max_employees: Maximum number of employees (0 = no upper bound)
        funding_stage: e.g. "Seed", "Series A", "Series B"
        tech_stack: Comma-separated technologies (e.g. "Salesforce,HubSpot,AWS")
        keywords: Free-text keywords to narrow results (e.g. "AI-native", "remote-first")
        page: Page number for pagination (default 0)
        size: Number of results per page (default 10)
    """
    api_key = os.environ.get("AI_ARK_API_KEY")
    if not api_key:
        return "Error: AI_ARK_API_KEY environment variable is not set."

    try:
        url = "https://api.ai-ark.com/api/developer-portal/v1/companies"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-TOKEN": api_key,
        }

        # All filters go inside the "account" object per the API spec
        account = {}

        # Industry filter
        if industry:
            normalized = _normalize_industry(industry)
            account["industries"] = {
                "any": {"include": {"mode": "WORD", "content": [normalized]}}
            }

        # Location filter — simple string array
        if location:
            account["location"] = {"any": {"include": [location]}}

        # Employee size filter
        if min_employees > 0 or max_employees > 0:
            emp_range = {}
            if min_employees > 0:
                emp_range["start"] = min_employees
            if max_employees > 0:
                emp_range["end"] = max_employees
            account["employeeSize"] = {"type": "RANGE", "range": [emp_range]}

        # Funding stage filter — uses enum values like SERIES_A
        if funding_stage:
            enum_val = _normalize_funding(funding_stage)
            if enum_val:
                account["funding"] = {"type": [enum_val]}

        # Technologies filter
        if tech_stack:
            techs = [t.strip() for t in tech_stack.split(",")]
            account["technologies"] = {
                "any": {"include": {"mode": "WORD", "content": techs}}
            }

        # Keyword filter
        if keywords:
            account["keyword"] = {
                "any": {
                    "include": {
                        "sources": [
                            {"mode": "SMART", "source": "DESCRIPTION"},
                            {"mode": "WORD", "source": "KEYWORD"},
                        ],
                        "content": [keywords],
                    }
                }
            }

        payload = {
            "page": page,
            "size": size,
        }
        if account:
            payload["account"] = account

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Response uses "content" as the array key (per API spec)
        companies = (
            data.get("content")
            or data.get("companies")
            or data.get("results")
            or data.get("data")
            or []
        )

        total = data.get("totalElements", len(companies))

        if not companies:
            return "No companies found matching the given filters. Try broadening your criteria."

        lines = [
            f"Found {total} total matches. Showing {len(companies)} companies (page {page}):\n"
        ]
        for c in companies:
            summary = c.get("summary", {})
            link = c.get("link", {})
            staff = summary.get("staff", {})

            name = summary.get("name") or "Unknown"
            description = summary.get("description") or summary.get("seo") or ""
            if len(description) > 150:
                description = description[:150] + "..."

            domain = link.get("domain") or link.get("website") or "N/A"
            total_staff = staff.get("total")
            range_start = staff.get("range", {}).get("start")
            employees = total_staff or range_start or "N/A"

            industry_val = (
                summary.get("industry") or (c.get("industries") or ["N/A"])[0]
            )
            founded = summary.get("founded_year") or "N/A"

            hq = c.get("location", {}).get("headquarter", {})
            city = hq.get("city", "")
            country = hq.get("country", "")
            hq_str = ", ".join(filter(None, [city, country])) or "N/A"

            # Funding info from financial.funding
            financial = c.get("financial", {})
            funding_info = financial.get("funding", {})
            funding_type = funding_info.get("type", "")
            last_amount = funding_info.get("last_amount")
            funding_str = funding_type
            if last_amount:
                funding_str += f" (last: ${last_amount:,})"

            techs = c.get("technologies", [])
            tech_names = ", ".join(t.get("name", "") for t in techs[:3]) or "N/A"

            lines.append(
                f"• {name} ({domain})\n"
                f"  HQ: {hq_str} | Employees: {employees} | Industry: {industry_val} | Founded: {founded}\n"
                f"  Funding: {funding_str or 'N/A'} | Tech: {tech_names}\n"
                f"  {description}\n"
            )

        return "\n".join(lines)

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        body_text = e.response.text[:400]
        if status == 401:
            return "AI Ark auth failed (401) — check X-TOKEN header and AI_ARK_API_KEY value."
        if status == 422:
            return f"AI Ark rejected request body (422). Response: {body_text}"
        return f"AI Ark API error {status}: {body_text}"
    except Exception as e:
        return f"Error in search_companies: {str(e)}"


@tool
def get_company_news(company_name: str, max_articles: int = 5) -> str:
    """
    Fetch recent news articles about a specific company using NewsAPI.
    Use this to surface trigger events — funding rounds, leadership changes,
    product launches, layoffs, or expansions — as timely outreach hooks.

    Args:
        company_name: The name of the company to search news for
        max_articles: Number of recent articles to return (default 5, max 10)
    """
    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        return "Error: NEWS_API_KEY environment variable is not set."

    try:
        max_articles = min(max_articles, 10)
        params = {
            "q": f'"{company_name}"',
            "sortBy": "publishedAt",
            "pageSize": max_articles,
            "language": "en",
            "apiKey": api_key,
        }

        response = requests.get(
            "https://newsapi.org/v2/everything", params=params, timeout=15
        )
        response.raise_for_status()
        data = response.json()

        articles = data.get("articles", [])
        if not articles:
            return f"No recent news found for '{company_name}'."

        lines = [f"Recent news for {company_name} ({len(articles)} articles):\n"]
        for i, article in enumerate(articles, 1):
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown source")
            published = article.get("publishedAt", "")[:10]
            url = article.get("url", "")
            description = article.get("description") or ""
            if len(description) > 200:
                description = description[:200] + "..."

            lines.append(
                f"{i}. [{source}] {title}\n"
                f"   Published: {published}\n"
                f"   {description}\n"
                f"   URL: {url}\n"
            )

        return "\n".join(lines)

    except requests.exceptions.HTTPError as e:
        return f"NewsAPI error: {e.response.status_code} — {e.response.text}"
    except Exception as e:
        return f"Error in get_company_news: {str(e)}"


@tool
def qualify_and_summarize(
    company_name: str,
    company_domain: str = "",
    industry: str = "",
    employee_count: str = "",
    funding_stage: str = "",
    recent_news_summary: str = "",
) -> str:
    """
    Generate a concise ICP qualification summary and suggested outreach angle.
    Use AFTER gathering company details and news.

    Args:
        company_name: Name of the company
        company_domain: Website/domain
        industry: Industry the company operates in
        employee_count: Size of the company
        funding_stage: Current funding stage (e.g. SERIES_B)
        recent_news_summary: Brief summary of recent news or trigger events
    """
    try:
        lines = [
            f"=== ICP Qualification Brief: {company_name} ===",
            "",
            f"🏢 Company:       {company_name}",
            f"🌐 Domain:        {company_domain or 'N/A'}",
            f"🏭 Industry:      {industry or 'N/A'}",
            f"👥 Team Size:     {employee_count or 'N/A'}",
            f"💰 Funding Stage: {funding_stage or 'N/A'}",
            "",
            "📰 Trigger Events / Recent News:",
            (
                recent_news_summary
                if recent_news_summary
                else "  No recent news provided."
            ),
            "",
            "✅ ICP Fit Assessment:",
        ]

        fit_signals = []
        if funding_stage and any(
            s in funding_stage.upper()
            for s in ["SERIES_A", "SERIES_B", "SERIES_C", "VENTURE"]
        ):
            fit_signals.append("  • Active funding stage — budget likely available")
        if recent_news_summary and any(
            kw in recent_news_summary.lower()
            for kw in [
                "raised",
                "funding",
                "launched",
                "hired",
                "expanded",
                "partnership",
            ]
        ):
            fit_signals.append("  • Positive trigger event — strong hook for outreach")
        if employee_count:
            try:
                emp = int(
                    "".join(filter(str.isdigit, str(employee_count).split("-")[0]))
                )
                if 50 <= emp <= 1000:
                    fit_signals.append(
                        "  • Mid-market size — ideal for consultative sales"
                    )
            except Exception:
                pass

        lines += (
            fit_signals
            if fit_signals
            else ["  • Review manually — no strong ICP signals auto-detected"]
        )
        lines += [
            "",
            "💡 Suggested Outreach Angle:",
            "  Use the most recent trigger event as your opening hook.",
            "  Reference their growth/funding/launch and tie it to your value prop.",
            "  Keep first message to 3 sentences: hook → relevance → CTA.",
        ]

        return "\n".join(lines)

    except Exception as e:
        return f"Error in qualify_and_summarize: {str(e)}"
