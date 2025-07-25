from services.story_processor import create_graph, set_process_id

def create_finalstate(story_text, process_id=None):
    """
    Create the final state of the story processing workflow.
    
    Args:
        story_text (str): The story text to process
        process_id (str, optional): Process ID for logging
        
    Returns:
        dict: The final state of the workflow.
    """
    # Set process ID for logging if provided
    if process_id:
        set_process_id(process_id)
    
    graph = create_graph()

    initial_state = {"story_text": story_text}

    final_state = graph.invoke(initial_state)
    return final_state