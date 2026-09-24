from multiprocessing import Process, Pipe
import traceback

def timeout(seconds):
    def decorator(func):
        def wrapper(*args, **kwargs):
            parent_conn, child_conn = Pipe()
            # Use a try-except block inside the lambda function to handle exceptions
            def target_function():
                try:
                    result = func(*args, **kwargs)
                    child_conn.send(result)
                except Exception as e:
                    # You could log the exception here or handle it as needed
                    child_conn.send(f"Error: {str(e)}\n{traceback.format_exc()}")

            p = Process(target=target_function)
            try:
                p.start()
                p.join(seconds)
                if p.is_alive():
                    p.terminate()  # Forcefully terminate the process
                    p.join()
                    raise TimeoutError("Function call timed out")  # Raise a TimeoutError on timeout
                else:
                    result = parent_conn.recv()
                    if isinstance(result, str) and result.startswith("Error:"):
                        # Handle the error sent from the child process
                        raise Exception(result)
                    return result
            except Exception as e:
                # Handle exceptions or re-raise them
                raise e
        return wrapper
    return decorator