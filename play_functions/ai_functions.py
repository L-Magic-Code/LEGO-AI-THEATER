from google import genai
from google.genai import types #type:ignore
import logging
import json
import pathlib


script_structure = {
    "type" : "object",
    "properties" : {
        "setup" : {
            "type" : "object",
            "properties" : {
                "play-name" : {"type" : "string"},
                "actors" : {
                    "type" : "object",
                    "properties" : {
                        "actor_1" : {
                            "type" : "array",
                            "items" : {"type" : "string"},
                            "minItems" : 2,
                            "maxItems" : 2
                        },
                        "actor_2" : {
                            "type" : "array",
                            "items" : {"type" : "string"},
                            "minItems" : 2,
                            "maxItems" : 2
                        },
                        "flying_item" : {
                            "type" : "array",
                            "items" : {"type" : "string"},
                            "minItems" : 2,
                            "maxItems" : 2
                        },
                        "turning_item" : {
                            "type" : "array",
                            "items" : {"type" : "string"},
                            "minItems" : 2,
                            "maxItems" : 2
                        }
                    },
                    "required" : ["actor_1", "actor_2", "flying_item", "turning_item"]
                }
            },
            "required" : ["actors"]
        },
        "scenes" : {
            "type" : "array",
            "items" : {
                "type" : "object",
                "properties" : {
                    "backdrop" : {"type" : "string"},
                    "background_music" : {"type" : "string"},
                    "actions" : {
                        "type" : "array",
                        "items" : {"type" : "string"}
                    }
                },
                "required" : ["backdrop", "actions"]
            }
        }
    },
    "required" : ["setup", "scenes"]
}




BASE_DIR = pathlib.Path(__file__).resolve().parent.parent

def save_feedback(feedback : str):
    """
    Saves feedback into the user_feedback.txt file.
    Args:
        feedback (str): The feedback to save into the user_feedback.txt file.
    """
    with open(BASE_DIR / 'user_feedback.txt', 'a') as opened_file:
        opened_file.write( "\n\n" + feedback)
        
class AI:
    def __init__(self):
        """
        Sets up the Client and configuration.
        """
                
        self.pathlib_config_file = BASE_DIR / "config.json"

        with open(self.pathlib_config_file, "r", encoding="utf-8") as config_file:
            self.config = json.load(config_file)
        
        self.client = genai.Client() 

        logging.basicConfig(
            level=getattr(logging, self.config["log_level"]),
            format="%(filename)s - %(levelname)s - %(message)s"
        )

    def generate_script(self, prompt : str) -> dict:
        """
        Generates a script in JSON and returns it as a dict.
        Args:
            prompt (str): The prompt for the play, that will be sent to google's genai.
        Returns:
            response (dict):  The generated script.
        """
        # Get the raw response from Google GenAI
        with open(BASE_DIR / 'ai_instructions.txt', "r") as opened_file:
            system_instruction = opened_file.read()

        feedback_file = BASE_DIR / 'user_feedback.txt'
        if not feedback_file.exists() or feedback_file.is_dir():
            logging.info("No feedback file found! Creating one now...")
            with open(BASE_DIR / 'user_feedback.txt', "w") as opened_file:
                pass 
        with open(feedback_file, "r") as opened_file:
            user_feedback = opened_file.read()

        system_instruction = system_instruction + "\n\nHere is some feedback that people have said about your previous plays, try to improve your plays based on this feedback: \n" + user_feedback

        raw_respone = self.client.models.generate_content(
            contents=prompt,
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=script_structure,
                system_instruction=system_instruction
            )
        )
        return json.loads(raw_respone.text)

    def save_script(self, script: dict):
        """
        Saves a script to a file.
        Args:
            script (dict): the script to save
        Returns:
            pathlib.Path object of the file the script has been saved to
        """
        name = script["setup"]["play-name"]
        name = name.replace(" ", "_")
        number = 1
        script_name_not_resolved = True

        while script_name_not_resolved:
            script_name = name + '_' + str(number) + '.json'
            if pathlib.Path(BASE_DIR / 'saved_scripts' / script_name).exists():
                number += 1
                continue
            else:
                logging.info(f"{script_name} available! Saving script to saved_scripts/{script_name}...")
                break

        with open(BASE_DIR / 'saved_scripts' / script_name, 'w') as opened_file:
            json.dump(script, opened_file, indent=4)

        logging.info("Filed saved successfully!")
        return BASE_DIR / 'saved_scripts' / script_name
    
if __name__ == '__main__':
    gemini = AI()
    script = gemini.generate_script("A very short script for a play about a robot that eats sticks. Use all actors and props.")
    print(script)
    gemini.save_script(script)