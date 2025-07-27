import openai
import os
from dotenv import load_dotenv

load_dotenv()

class Agent:
    """Simple Agent class for company analysis"""
    
    def __init__(self, name, instructions):
        self.name = name
        self.instructions = instructions
        self.api_key = os.getenv("OPENAI_API_KEY")
        
    def query(self, user_input):
        """Query the agent with user input"""
        if not self.api_key:
            raise Exception("OpenAI API key not configured")
            
        client = openai.OpenAI(api_key=self.api_key)
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": self.instructions},
                {"role": "user", "content": user_input}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        
        return AgentResult(
            final_output=response.choices[0].message.content,
            usage=response.usage if hasattr(response, 'usage') else None
        )

class AgentResult:
    """Simple result class to match expected interface"""
    
    def __init__(self, final_output, usage=None):
        self.final_output = final_output
        self.usage = usage

class Runner:
    """Simple Runner class for synchronous agent execution"""
    
    @staticmethod
    def run_sync(agent, query):
        """Run agent query synchronously"""
        return agent.query(query)