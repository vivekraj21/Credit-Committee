---
title: "Credit-Committee"
emoji: "💼"
sdk: gradio
python_version: "3.10"
app_file: app.py
pinned: false
---

# 🏢 AI Corporate Credit Committee
### *Where AI Agents Collaborate like Executives*

**Hackathon Project for the Band of Agents Hackathon**

The AI Corporate Credit Committee is a digital boardroom where multiple autonomous AI agents—representing different banking roles—work together to approve or reject corporate loan applications. 

This is **not** a chatbot. It is a native **Band-powered AI organization**.

---

## 🚀 The Vision
In a real bank, corporate loans aren't approved by a single person; they are debated by a committee. We have recreated this complex social workflow using:
- **[Band Protocol](https://band.ai/)**: The collaboration layer. Agents join rooms, share context, and debate.
- **[LangGraph](https://www.langchain.com/langgraph)**: The orchestration layer. Manages the meeting flow from analysis to resolution.
- **[Groq (Llama 3.3 70B)](https://groq.com/)**: The intelligence layer. Providing near-instant executive-level reasoning.

---

## 🛠️ Key Components

### 1. The Agent Council
Every member is an expert defined in a central `agents.json` configuration:
- **Chairman**: Moderates the meeting, detects conflicts, and drives consensus.
- **Financial Analyst**: Deep dives into revenue, cash flow, and repayment.
- **Credit Risk Officer**: Evaluates leverage ratios and credit scores.
- **Compliance Officer**: Ensures every loan follows banking policies.

### 2. Band-Native Collaboration
- **Dynamic Presence**: Agents visibly join a dedicated Band room for every loan application.
- **Shared Context**: Findings are published to the room context, allowing agents to "read" each other's work.
- **Messaging History**: Every debate and conflict resolution is stored in the room's message history.

### 3. Boardroom Dashboard
A premium **Gradio** interface that visualizes the committee meeting as it happens. Watch as agents join, publish findings, detect conflicts, and reach a final board resolution.

---

## 📦 Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Credit-Committee.git
   cd Credit-Committee
   ```

2. **Setup virtual environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Configure API Keys:**
   Create a `.env` file in the root:
   ```env
   GROQ_API_KEY=your_key
   BAND_API_KEY=your_key
   ```

4. **Launch the Boardroom:**
   ```bash
   python src/frontend/app.py
   ```
   Open `http://localhost:7860` in your browser.

---

## 🏛️ Design Policy
- **Modular Agents**: Add new specialist agents just by editing a JSON file.
- **Blackboard Pattern**: All agents write to and read from the shared Band state.
- **Supervisor-less Interaction**: Agents communicate through the room, not just through a central controller.

---

**Developed for the Band of Agents Hackathon.**
Integrating LangGraph logic with Band collaboration.
