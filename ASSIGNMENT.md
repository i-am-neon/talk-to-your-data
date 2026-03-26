# Stage 2 — Take-Home Assignment: Talk to Your Data

**Deadline**: 7 days from 2026-03-24 (by 2026-03-31)
**Submit to**: Anton.Gorshkov@genesiscomputing.ai
**Subject line**: "Take-Home Submission -- Tommy Wilczek"
**Time expectation**: 4-6 hours

## Overview

Build and deploy a natural language data agent that allows users to ask questions about a dataset in plain English and receive structured answers. Tests ability to work with modern AI-assisted development tools, build functional LLM-powered applications, and deploy production-ready software.

## What to Build

A web application where users can ask natural language questions about a provided dataset. The agent should:
1. Interpret the question
2. Generate the appropriate query (SQL, pandas, or similar)
3. Execute it
4. Return an answer along with the underlying query used

The answer can be plain text, a table, or a visualization -- be creative.

## Sample Dataset

`sample_data.csv` — a fictional dataset of 500 SaaS company metrics including:
- Company name
- ARR
- Employee count
- Industry vertical
- Founding year
- Churn rate
- Growth rate

Can also create own dataset -- just include it in submission.

**CSV download link**: (provided in PDF, needs to be downloaded separately)

## Example Interactions

- "What's the average ARR for fintech companies?"
- "Which company has the highest growth rate?"
- "Show me companies founded after 2020 with less than 5% churn."
- "How many companies have more than 100 employees?"

## Required Features

1. Web interface where users can type natural language questions
2. Integration with their LiteLLM Proxy
3. Query generation and execution against the dataset
4. Display the answer
5. Basic error handling for malformed questions or failed queries
6. **Deployed to a publicly accessible URL**

## LLM Proxy

- **URL**: https://litellm-production-f079.up.railway.app/
- **API Key**: (redacted — see .env)

## Encouraged Tools

They **strongly encourage** AI-assisted development tools. This is a test of whether you can effectively leverage modern tools to ship quality software quickly.

- Claude Code, Cursor, GitHub Copilot, Amp or similar
- Claude, ChatGPT, or other LLMs for design decisions and debugging
- Any frameworks, libraries, or templates

## Evaluation Criteria

| Criteria | What They Look For |
|----------|-------------------|
| **AI Tool Usage** | Effective use of AI coding assistants. Commit history shows thoughtful iteration. |
| **Functionality** | The app works. Questions get reasonable answers. Edge cases handled gracefully. |
| **Code Quality** | Clean structure, readable code, sensible abstractions. Not over-engineered, not spaghetti. |
| **Deployment** | Successfully deployed and accessible. Reasonable hosting choices. (hint: use something easy) |
| **Technical Decisions** | Thoughtful choices about architecture and frameworks. Can articulate trade-offs. |

## Deliverables

1. **Live URL** where they can test the deployed application
2. **Public GitHub repo** -- keep commit history intact (they want to see how you worked)
3. **Brief README** (max 500 words) covering:
   - Which AI tools you used and how
   - Interesting challenges you encountered
   - What you'd improve with more time
   - Any design decisions worth noting
4. **Loom video** (max 5 minutes) -- demo the app, talk about design choices, explain how it works

## Bonus Points (Optional)

- Conversation memory (follow-up questions that reference previous context)
- Support for multiple data sources or file uploads
- Data visualization for query results
- Other creative additions

> "A solid implementation of the core requirements is more valuable than a sprawling feature set."

## Interview Process (Full)

| Stage | Description |
|-------|-------------|
| 1 | Initial Screen w/ Anton -- experience, communication, fit (30 min) -- **PASSED** |
| 2 | Take Home Assignment -- **THIS** |
| 3 | Technical Evaluation w/ Team Member + Fit w/ Gabriel (45 min) |
| 4 | Technical Evaluation w/ Lead Architect + Fit w/ Yuly (45 min) |
| 5 | Overall Fit with 2 co-founders (Matt & Justin), 30 min each |
| 6 | [Optional] Additional interviews if concerns from rounds 2-4 |
| 7 | Reference Request + Reference Check w/ Anton (10 min) |
| 8 | Hire/No Hire decision |
| 9 | Offer |

**Note**: Stages 2 & 3 can run in parallel. Ideally take-home is done before scheduling Stage 3/4.

- **Stage 3 (Gabriel)**: https://calendar.app.google/F6fW2R4JaGTzRrJr8 (include resume)
- **Stage 4 (Yuly)**: https://calendar.app.google/SKxzjXZRPe7xNfCEA
