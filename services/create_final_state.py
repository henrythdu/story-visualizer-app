import asyncio
import time
from services.story_processor import create_graph, set_process_id, set_log_storage, initialize_models

async def create_finalstate_async(story_text, process_id=None, log_storage=None, api_key=None):
    """
    Create the final state of the story processing workflow asynchronously.
    
    Args:
        story_text (str): The story text to process
        process_id (str, optional): Process ID for logging
        log_storage (dict, optional): Log storage reference
        api_key (str, optional): Google API key for model initialization
        
    Returns:
        dict: The final state of the workflow.
    """
    print(f"[DEBUG] create_finalstate_async called with process_id: {process_id}")  # Debug
    # Set process ID for logging if provided
    if process_id:
        set_process_id(process_id)
        print(f"[DEBUG] Set process_id: {process_id}")  # Debug
    
    # Set log storage reference if provided
    if log_storage:
        set_log_storage(log_storage)
        print("[DEBUG] Set log_storage")  # Debug
    
    # Initialize models with provided API key
    print(f"[DEBUG] Initializing models with api_key: {'provided' if api_key else 'None'}")  # Debug
    initialize_models(api_key)
    print("[DEBUG] Finished initializing models")  # Debug
    
    graph = create_graph()
    print("[DEBUG] Created graph")  # Debug

    initial_state = {"story_text": story_text}
    print("[DEBUG] Created initial_state")  # Debug

    print("[DEBUG] Invoking graph asynchronously")  # Debug
    # Use astream to get real-time updates
    final_state = {}
    try:
        async for chunk in graph.astream(initial_state):
            for node, state in chunk.items():
                # Update log with completed step
                if process_id and log_storage and process_id in log_storage:
                    log_storage[process_id].append(f"Completed processing step: {node}")
                    # Force flush to ensure logs are sent immediately
                    import sys
                    sys.stdout.flush()
                    sys.stderr.flush()
                final_state = {**final_state, **state}
                # Yield control to allow event loop to process log streaming
                await asyncio.sleep(0.01)
    except Exception as e:
        print(f"[DEBUG] Error during graph streaming: {e}")
        if process_id and log_storage and process_id in log_storage:
            log_storage[process_id].append(f"Error during processing: {str(e)}")
        raise
    
    print("[DEBUG] Graph async streaming completed")  # Debug
    return final_state

def create_finalstate(story_text, process_id=None, log_storage=None, api_key=None):
    """
    Create the final state of the story processing workflow (synchronous version).
    
    Args:
        story_text (str): The story text to process
        process_id (str, optional): Process ID for logging
        log_storage (dict, optional): Log storage reference
        api_key (str, optional): Google API key for model initialization
        
    Returns:
        dict: The final state of the workflow.
    """
    print(f"[DEBUG] create_finalstate called with process_id: {process_id}")  # Debug
    # Set process ID for logging if provided
    if process_id:
        set_process_id(process_id)
        print(f"[DEBUG] Set process_id: {process_id}")  # Debug
    
    # Set log storage reference if provided
    if log_storage:
        set_log_storage(log_storage)
        print("[DEBUG] Set log_storage")  # Debug
    
    # Initialize models with provided API key
    print(f"[DEBUG] Initializing models with api_key: {'provided' if api_key else 'None'}")  # Debug
    initialize_models(api_key)
    print("[DEBUG] Finished initializing models")  # Debug
    
    graph = create_graph()
    print("[DEBUG] Created graph")  # Debug

    initial_state = {"story_text": story_text}
    print("[DEBUG] Created initial_state")  # Debug

    print("[DEBUG] Invoking graph")  # Debug
    final_state = graph.invoke(initial_state)
    print("[DEBUG] Graph invocation completed")  # Debug
    return final_state