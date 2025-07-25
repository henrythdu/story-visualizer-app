from services.story_processor import create_graph

def create_finalstate(story_text):
    """
    Create the final state of the story processing workflow.
    
    Returns:
        dict: The final state of the workflow.
    """
    graph = create_graph()

    initial_state = {"story_text": story_text}

    final_state = graph.invoke(initial_state)
    return final_state