def main():
    print("Starting...")
#   Import modules
    from play_functions import robot_functions
    from play_functions import ai_functions
    import pathlib
    import json
    print("\n\n\n")
    
#   Load configuration file
    BASE_DIR = pathlib.Path(__file__).resolve().parent
    pathlib_config_file = BASE_DIR / "config.json"

    with open(pathlib_config_file, "r") as config_file:
        config = json.load(config_file)

#   Add feedback file if it doesn't exist 
    feedback_file = BASE_DIR / "user_feedback.txt"
    if not feedback_file.is_file():
        with open(feedback_file, "w") as f:
            pass
 
#   Get script
    if config["script"] == "gemini-generate":
        gemini = ai_functions.AI()
        prompt = input("What would you like your play to be about?\n")
        script = gemini.generate_script(prompt)
        script_file = gemini.save_script(script)
    else:
        script_file_with_extension = config["script"] + ".json"
        script_file = pathlib.Path(BASE_DIR / "saved_scripts" / script_file_with_extension)
        if not script_file.is_file():
            raise FileNotFoundError(f"{BASE_DIR}/saved_scripts/{config['script']} is not a file!")
    
    with robot_functions.Robot() as theater:
        theater.stop_motors()    

        theater.load_script(script_file)
    
        theater.stop_motors()    

        theater.start()
        theater.stop_motors()

    feedback = input("Do you have feedback for this play?\n")
    if feedback:
        ai_functions.save_feedback(feedback)
        print("Thank you for your feedback! It will be used to improve future plays.")


if __name__ == '__main__':
    main()