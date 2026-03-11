import os
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage

from tools import search_companies, get_company_news, qualify_and_summarize


SYSTEM_PROMPT = """You are ICP Qualifier, an expert B2B sales intelligence assistant built for GenAIlytics.

Your job is to help sales reps identify and qualify Ideal Customer Profile (ICP) companies, surface recent trigger events, and generate actionable outreach briefs.

Your capabilities:
1. search_companies — Search for target companies using filters: industry, location, employee size, funding stage, and tech stack. Use this when a rep describes their ICP or asks for a list of target accounts.
2. get_company_news — Fetch the latest news about a specific company. Use this to find trigger events (funding, launches, hires, expansions) that make outreach timely and relevant.
3. qualify_and_summarize — Generate a full ICP qualification brief with a suggested outreach angle. Use this AFTER gathering company details and news to produce a final brief for the rep.

Guidelines:
- Always use tools to fetch real data. Never make up company details or news.
- When a rep gives you ICP criteria, start with search_companies to build a target list.
- For each company of interest, call get_company_news to find trigger events.
- Always finish with qualify_and_summarize to give the rep a ready-to-use brief.
- If a tool returns an error, explain what went wrong and suggest a fix.
- Be concise, structured, and sales-ready in your responses.
- Format output clearly — use bullet points and sections so reps can scan quickly.
- If the user just says "hello" or asks what you can do, explain your capabilities clearly.
"""


class Agent:
    def __init__(self):
        self.name = "ICP Qualifier Agent"

        llm = ChatOpenAI(
            model="gpt-4o", temperature=0.1, api_key=os.environ.get("OPENAI_API_KEY")
        )

        tools = [search_companies, get_company_news, qualify_and_summarize]

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_openai_functions_agent(llm=llm, tools=tools, prompt=prompt)

        self.executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=6,
        )

    def process_message(self, message: str) -> str:
        try:
            result = self.executor.invoke({"input": message})
            return result.get("output", "No response generated.")
        except Exception as e:
            return f"Agent error: {str(e)}"
