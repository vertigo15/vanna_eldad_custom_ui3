"""Azure OpenAI LLM service for Vanna 2.0."""

from openai import AzureOpenAI
from typing import Dict, Any, List, Optional, AsyncGenerator
import asyncio
import json

from vanna.core.llm.base import LlmService
from vanna.core.llm.models import LlmRequest, LlmResponse, LlmMessage, ToolCall


class AzureOpenAILlmService(LlmService):
    """
    Azure OpenAI LLM service for Vanna 2.0.
    Provides text generation capabilities using Azure OpenAI.
    Implements Vanna's LlmService interface.
    """
    
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str = "2025-01-01-preview"
    ):
        super().__init__()
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        self.deployment = deployment
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response from Azure OpenAI.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional tool definitions for function calling
            
        Returns:
            Response dict with 'content', 'tool_calls', etc.
        """
        loop = asyncio.get_event_loop()
        
        params = {
            "model": self.deployment,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        
        response = await loop.run_in_executor(
            None,
            lambda: self.client.chat.completions.create(**params)
        )
        
        choice = response.choices[0]
        result = {
            "content": choice.message.content or "",
            "finish_reason": choice.finish_reason,
        }
        
        # Handle tool calls if present
        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in choice.message.tool_calls
            ]
        
        return result
    
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from Azure OpenAI.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Yields:
            Content chunks as they arrive
        """
        loop = asyncio.get_event_loop()
        
        # Create stream in executor
        stream = await loop.run_in_executor(
            None,
            lambda: self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                stream=True
            )
        )
        
        # Yield chunks
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    # Vanna 2.0 Interface Methods
    def send_request(self, request: LlmRequest) -> LlmResponse:
        """
        Send request to LLM (Vanna 2.0 interface).
        
        Args:
            request: LlmRequest object
            
        Returns:
            LlmResponse object
        """
        # Convert Vanna's Message objects to dicts for OpenAI
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]
        
        params = {
            "model": self.deployment,
            "messages": messages,
            "temperature": request.temperature if hasattr(request, 'temperature') else 0.7,
            "max_completion_tokens": request.max_tokens if hasattr(request, 'max_tokens') else 4096,
        }
        
        # Add tools if provided
        if hasattr(request, 'tools') and request.tools:
            params["tools"] = request.tools
            params["tool_choice"] = "auto"
        
        # Make synchronous call
        response = self.client.chat.completions.create(**params)
        
        choice = response.choices[0]
        
        # Build LlmResponse
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        type=tc.type,
                        function_name=tc.function.name,
                        function_arguments=tc.function.arguments
                    )
                )
        
        return LlmResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            metadata={
                "model": self.deployment,
                "usage": response.usage.model_dump() if response.usage else {}
            }
        )
    
    async def stream_request(self, request: LlmRequest) -> AsyncGenerator[LlmResponse, None]:
        """
        Stream request to LLM (Vanna 2.0 interface).
        
        Args:
            request: LlmRequest object
            
        Yields:
            LlmResponse chunks
        """
        # Convert messages
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]
        
        loop = asyncio.get_event_loop()
        
        # Create stream
        stream = await loop.run_in_executor(
            None,
            lambda: self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=request.temperature if hasattr(request, 'temperature') else 0.7,
                max_completion_tokens=request.max_tokens if hasattr(request, 'max_tokens') else 4096,
                stream=True
            )
        )
        
        # Yield chunks as LlmResponse
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield LlmResponse(
                    content=chunk.choices[0].delta.content,
                    tool_calls=[],
                    finish_reason=None,
                    metadata={"chunk": True}
                )
