import ev3_dc as ev3
import edge_tts
import asyncio
import json
import pathlib
import logging
import subprocess
import tempfile
import uuid
import threading
import time
import cv2
import pygame

class Robot:
    def __init__(self):
        """
        Initializes the robot.
        """

        self.BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
                        
        self.pathlib_config_file = self.BASE_DIR / "config.json"

        with open(self.pathlib_config_file, "r", encoding="utf-8") as config_file:
            self.config = json.load(config_file)

        logging.basicConfig(
            level=getattr(logging, self.config["log_level"]),
            format="%(filename)s - %(levelname)s - %(message)s"
        )

        try:
            if self.config["ev3_hub_protocol"].upper() not in ["USB", "BLUETOOTH"]:
                raise ValueError("Invalid EV3 HUB protocol in config.json. Please use 'USB' or 'BLUETOOTH'.")
            elif self.config["ev3_hub_protocol"].upper() == "USB":
                self.robot = ev3.EV3(protocol=getattr(ev3, self.config["ev3_hub_protocol"].upper()))
            elif self.config["ev3_hub_protocol"] == "BLUETOOTH":
                self.robot = ev3.EV3(protocol=getattr(ev3, self.config["ev3_hub_protocol"].upper()), host=str(self.config["ev3_hub_mac_address"]))
        except ev3.exceptions.NoEV3:
            logging.critical("EV3 HUB NOT CONNECTED!")
            raise ev3.exceptions.NoEV3("Robot not connected!")
        
        not_connected_motors = []
        try:
            self.turning_object = ev3.Motor(ev3_obj=self.robot, port=getattr(ev3, self.config["turning_object_motor_port"]))
        except ev3.exceptions.MotorError:
            not_connected_motors.append("turning object motor")
        
        try:
            self.figure_one = ev3.Motor(ev3_obj=self.robot, port=getattr(ev3, self.config["figure_one_motor_port"]))
        except ev3.exceptions.MotorError:
            not_connected_motors.append("figure 1 object motor")
                    
        try:
            self.figure_two = ev3.Motor(ev3_obj=self.robot, port=getattr(ev3, self.config["figure_two_motor_port"]))
        except ev3.exceptions.MotorError:
            not_connected_motors.append("figure two object motor")
                    
        try: 
            self.flying_object = ev3.Motor(ev3_obj=self.robot, port=getattr(ev3, self.config["flying_object_motor_port"]))
        except ev3.exceptions.MotorError:
            not_connected_motors.append("flying object motor")
                            
        if not_connected_motors:
            for motor in not_connected_motors:
                logging.critical(f"Motors not connected: {motor}")
            raise Exception("Motors not connected! Please make sure each cable is securly connected!")

        self.available_backgrounds = [
            "village_house",
            "village_in_flames_in_distance",
            "savana",
            "lake",
            "feilds",
            "cliff_overlook",
            "faraway_ruined_castle_in_distance",
            "faraway_ruined_castle_interior",
            "fancy_castle_room_1_interior",
            "fancy_castle_room_2_interior",
            "waiting_slide",
            "end_slide"
        ]

        self.available_music = [
            "calm_emotional_music",
            "calm_upbeat_music",
            "dark_mystery_music",
            "epic_action_music",
            "funky_fast_paced_music",
            "funny_conga_music",
            "funny_mischevious_music",
            "heroic-patriotic_music",
            "epic_climax_music",
            "no_music"
        ]

        self.available_sound_effects = [
            "base_drop",
            "birds_chirping",
            "explosion",
            "footsteps",
            "funny_boing",
            "magical_sparkle_woosh",
            "siren",
            "thunder",
            "all_sfx"
        ]

        self.use_screen = self.config["use_screen"]
 
        self._keep_running_jiggle_thread = False
        self._jiggle_thread_object = None

        self.flying_object.position = 0

        self.background_to_show = None
            
        self.current_song = None
        self.run_window = True

        pygame.init()

        self.sound = pygame.mixer
        self.sound.init()
        self.sound.music.set_volume(.1)

        base_drop_sfx = pygame.mixer.Sound(self.BASE_DIR / "sfx" / "base_drop.mp3")
        birds_chirping_sfx = pygame.mixer.Sound(self.BASE_DIR / "sfx" / "birds_chirping.mp3")
        explosion_sfx = pygame.mixer.Sound(self.BASE_DIR / "sfx" / "explosion.mp3")
        footsteps_sfx = pygame.mixer.Sound(self.BASE_DIR / "sfx" / "footsteps.mp3")
        funny_boing_sfx = pygame.mixer.Sound(self.BASE_DIR / "sfx" / "funny_boing.mp3")
        magical_sparkle_woosh_sfx = pygame.mixer.Sound(self.BASE_DIR / "sfx" / "magical_sparkle_woosh.mp3")
        siren_sfx = pygame.mixer.Sound(self.BASE_DIR / "sfx" / "siren.mp3")
        thunder_sfx = pygame.mixer.Sound(self.BASE_DIR / "sfx" / "thunder.mp3")

        self._sfx_map = {
            "base_drop" : base_drop_sfx,
            "birds_chirping" : birds_chirping_sfx,
            "explosion" : explosion_sfx,
            "footsteps" : footsteps_sfx,
            "funny_boing" : funny_boing_sfx,
            "magical_sparkle_woosh" : magical_sparkle_woosh_sfx,
            "siren" : siren_sfx,
            "thunder" : thunder_sfx
        }

        self.play_music(self.config["start_music"])



        if self.use_screen:
            cv2.namedWindow("Theater", cv2.WINDOW_NORMAL)
            self.set_background('waiting_slide')
            cv2.imshow("Theater", self.background_to_show)
            print("Please move background widow to the theater's screen. Waiting for C to be pressed.")
            while cv2.waitKey(1) != ord("c"):
                time.sleep(.3)


    def load_script(self, script):
        """
        Loads script.
        This MUST be called before any other function can be called.
        Args:
            script (str): The json file (correctly structured) path to open and read.
        """
        with open(script, "r") as opened_file:
            self.script = json.load(opened_file)

        self.actors = self.script["setup"]["actors"]
        

        self.figure_one.position = 0
        self.figure_two.position = 0
        self.figure_move_map = {
            "offstage" : 0,
            "stage-left" : self.config["stage_left_position"],
            "stage-right" : self.config["stage_right_position"],
            "stage-center" : self.config["stage_center_position"] 
        }
        self.actor_voices_map = {
            self.actors["actor_1"][0] : self.actors["actor_1"][1],
            self.actors["actor_2"][0] : self.actors["actor_2"][1],
            self.actors["flying_item"][0] : self.actors["flying_item"][1],
            self.actors["turning_item"][0] : self.actors["turning_item"][1]
        }

        self.actor_motors_map = {
            self.actors["actor_1"][0] : self.figure_one,
            self.actors["actor_2"][0] : self.figure_two,
            self.actors["flying_item"][0] : self.flying_object,
            self.actors["turning_item"][0] : self.turning_object
        }




    def play_sound_effect(self, effect : str, loop : bool):
        """
        Starts playing a sound effect.
        Stops all sfx if effect is 'no_sfx'
        Args:
            effect (str): The available sound effect to play.
            loop (bool): Wether or not the audio should be looped.
        """
        if not effect in self.available_sound_effects:
            logging.error(f"{effect} is not an available sound effect!")
            return
        _effect_sound = self._sfx_map[effect]
        _effect_sound.play(loops=loop)

    def stop_sound_effect(self, effect : str):
        """
        Stop playing a sound effect.
        Stops all sfx if effect is 'no_sfx'
        Args:
            effect (str): The available sound effect to play.
            loop (bool): Wether or not the audio should be looped.
        """
        if not effect in self.available_sound_effects:
            logging.error(f"{effect} is not an available sound effect!")
        elif effect == 'all_sfx':
            self.sound.fadeout(1000)
            return
        
        _effect_sound = self._sfx_map[effect]
        _effect_sound.fadeout(1000)

    def play_music(self, song : str):
        """
        Starts or changes music.
        Args:
            song (str): The available song to play
        """
        if not song in self.available_music:
            logging.error(f"{song} is not an available song!")
            return
        self.current_song = song
        self.sound.music.fadeout(2000)
        if song == "no_music":
            return
        song = song + ".mp3"
        self.sound.music.load(self.BASE_DIR / "background_music" / song)
        self.sound.music.play(-1)


    def start(self):
        """
        Starts the play.
        """
        self.insert_actors()
        threading.Thread(target=self._play, daemon=False).start()
        if self.use_screen:
            self.window_loop()
        else:
            while self.run_window:
                time.sleep(.3)

    def stop_motors(self):
        """
        Stops all Mindstorms motors.
        """
        self.figure_one.stop(brake=True)
        self.figure_two.stop(brake=True)
        self.flying_object.stop(brake=self.config["flying_object_brake"])
        self.turning_object.stop(brake=self.config["spinning_object_brake"])

    def move(self, figure : str, amount : str):
        """
        Moves a figure to the designated place.

        Args:
            figure (str): The name of the actor you want to move. The names should be defined in the script's 'setup' section.
            amount (str): The place the actor should move to. This can be one of these: 'offstage', 'stage-left', 'stage-right', or 'stage-center'. 
        """

        if figure == self.actors["actor_1"][0] or figure == self.actors["actor_2"][0]:
            self.play_sound_effect("footsteps", True)
            self.actor_motors_map[figure].move_to(self.figure_move_map[amount], speed=self.config["move_speed"], brake=True).start(thread=False)
            self.stop_sound_effect("footsteps")

    def _jiggle_thread(self, figure : str):
        """
        Thread for _jiggle function.
        """
        while self._keep_running_jiggle_thread:
            self.actor_motors_map[figure].move_by(self.config["jiggle_degrees_range"], brake=True).start(thread=False)
            if not self._keep_running_jiggle_thread:
                break
            self.actor_motors_map[figure].move_by(self.config["jiggle_degrees_range"] * -1, brake=True).start(thread=False)

    def _jiggle(self, figure : str):
        """
        Jiggles a figure as a Thread.
        This may be useful for ilustrating a character talking.
        Args:
            figure (str): The name of the actor to jiggle.
        """
        self._keep_running_jiggle_thread = True
        self._jiggle_thread_object  = threading.Thread(target=self._jiggle_thread, args=[figure])
        self._jiggle_thread_object.start()

    def _end_jiggle(self, figure):
        """
        Stops jiggling a figure.
        Args:
            figure (str): The name of the actor to stop jiggling.
        """
        self._keep_running_jiggle_thread = False
        self._jiggle_thread_object.join()
        self.actor_motors_map[figure].stop(brake=True)
        self._jiggle_thread_object = None

    def speak(self, text : str, actor : str, jiggle : bool=True, specific_voice : bool=False):
        """
        Saves and plays edge_tts generated text-to-speech from a .mp3 file.

        Args:
            text (str): The text to translate into audio.
            actor (str): The actor that will say the translated text.
            jiggle (bool): Whether to jiggle the actor while speaking. Defaults to True.
            specific_voice (bool): Set to True only if you the actor is a specific edge_tts voice.
        """
        is_actor = actor == self.script["setup"]["actors"]["actor_1"][0] or actor == self.script["setup"]["actors"]["actor_2"][0]
        if not is_actor:
            jiggle = False

        tmp_directory = tempfile.gettempdir()
        audio_file = f"{uuid.uuid4()}.mp3"
        file = pathlib.Path(tmp_directory) /audio_file

        if not specific_voice:
            voice = self.actor_voices_map[actor]
        else:
            voice = actor
            jiggle = False

        attempts = self.config["tts_generate_attempts"]
        for x in range(attempts):
            try:
                communicate = edge_tts.Communicate(text=str(text), voice=str(voice))
                asyncio.run(communicate.save(str(file)))
                break
            except edge_tts.exceptions.NoAudioReceived:
                attempts -= 1
                logging.warning(f"Failed to generate voice audio! {attempts} attempts left!")
                if attempts == 0:
                    logging.error("Failed to generate voice audio after all attempts.")
                    return
                time.sleep(self.config["tts_generate_wait_time"] + (x + 1))

        if jiggle:
            self._jiggle(actor)
        
        subprocess.run([
            "ffplay",
            "-nodisp",
            "-autoexit",
            file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        pathlib.Path(file).unlink()
        if jiggle:
            self._end_jiggle(actor)

    def lower_flying_object(self):
        """
        Lowers the flying object.
        """
        self.flying_object.move_to(self.config["flying_object_drop_degrees"], speed=self.config["flying_object_speed"], brake=self.config["flying_object_brake"]).start(thread=self.config["flying_object_thread"])

    def raise_flying_object(self):
        """
        Raises the flying object.
        """
        self.flying_object.move_to(position=35, speed=self.config["flying_object_speed"], brake=self.config["flying_object_brake"]).start(thread=self.config["flying_object_thread"])

    def spin_spinning_object(self):
        """
        Spins the spinning rock the number of degrees.
        Args:
            degrees (int): The amount of degrees to spin the motor
        """
        self.turning_object.move_by(degrees=self.config["spinning_object_180_degree_turn"], speed=self.config["spinning_object_speed"], brake=self.config["spinning_object_brake"]).start(thread=self.config["spinning_object_thread"])

    def set_background(self, background : str):
        """
        Changes the screens background.
        Args:
            background (str): The name of the background to switch to.
        """
        if self.use_screen:
            if not background in self.available_backgrounds:
                logging.error(f"{background} is not an available background.")
            _background_with_extension = background + ".png"
            background = self.BASE_DIR / 'backgrounds' / _background_with_extension
            self.background_to_show = cv2.imread(background)
    
    def window_loop(self):
        """
        Loop that keeps the theater's windows up and running until run_window becomes False.
        """
        _last_shown = None
        while self.run_window:
            if self.background_to_show is not None and self.background_to_show is not _last_shown:
                cv2.imshow("Theater", self.background_to_show)
                _last_shown = self.background_to_show

            if cv2.waitKey(1) & 0xFF == ord('q'):
                pass
            time.sleep(.3)

    
    def _play(self):
        """
        Reads the script defined in initialazation and controls the robot acordingly.
        This function blocks while the play is running.
        """
        _scene_counter = 0

        self.speak(
            f"Welcome to L-Magic Cinema, the Worlds best Lego Theater! First, please familiarize yourselves with the nearest exits. Photos and videos are welcome, as long as it is not disturbing others. Thank you, and enjoy the show! And now, I present to you, {self.script['setup']['play-name']}!", 
            actor="en-US-AndrewNeural",
            specific_voice=True)
        self.play_music("no_music")
        time.sleep(1)
        self.play_sound_effect("base_drop", False)
        time.sleep(4)
        for scene in self.script["scenes"]:
            self.set_background(self.script["scenes"][_scene_counter]["backdrop"])
            song = self.script["scenes"][_scene_counter]["background_music"]
            if song != self.current_song:
                self.play_music(song)

            for action in self.script["scenes"][_scene_counter]["actions"]:                       
                action = action.split(maxsplit=2)

                if action[1] == "say":
                    self.speak(action[2], action[0], jiggle=self.config["jiggle_actors"])
            
                elif action[1] == "move":
                    self.move(action[0], action[2])

                elif action[1] == "lower":
                    self.lower_flying_object()

                elif action[1] == "raise":
                    self.raise_flying_object()

                elif action[1] == "spin":
                    self.spin_spinning_object()

                elif action[0] == "wait":
                    time.sleep(float(action[1]))
                
                elif action[1] == "change":
                    song = action[2]
                    if song != self.current_song:
                        self.play_music(song)

                elif action[0] == "play_effect":
                    effect = action[1]
                    loop = action[2] == "True"
                    self.play_sound_effect(effect, loop)
            
            self.exit_actors()
            _scene_counter += 1


#       Ends  the code.


        self.stop_sound_effect("all_sfx")
        self.play_music(self.config["end_music"])
        self.set_background("end_slide")
        time.sleep(5)
        self.enter_actors()
        self.speak("Thank you for watching! Please leave us your feedback on this play!", actor=self.script['setup']['actors']["actor_1"][0]) 
        time.sleep(.5)
        self.exit_actors()
        time.sleep(3)
        self.play_sound_effect("base_drop", False)
        time.sleep(2)
        self.play_music("no_music")
        self.run_window = False
        time.sleep(1)
        if self.use_screen:
            cv2.destroyAllWindows()

    def exit_actors(self):
        """
        Moves all actors offstage.
        """
        self.figure_one.move_to(0, speed=self.config["move_speed"], brake=self.config["figure_one_brake"]).start(thread=False)
        self.figure_two.move_to(0, speed=self.config["move_speed"], brake=self.config["figure_two_brake"]).start(thread=False)
        self.flying_object.move_to(0, speed=self.config["flying_object_speed"], brake=self.config["flying_object_brake"]).start(thread=False)
        self.turning_object.move_to(0, speed=self.config["spinning_object_speed"], brake=self.config["spinning_object_brake"]).start(thread=False)


    def enter_actors(self):
        """
        Moves all actors onstage.
        """
        self.figure_one.move_to(position=self.config["stage_left_position"], speed=self.config["move_speed"], brake=self.config["figure_one_brake"]).start(thread=False)
        self.figure_two.move_to(position=self.config["stage_right_position"], speed=self.config["move_speed"], brake=self.config["figure_two_brake"]).start(thread=False)
        self.flying_object.move_to(position=self.config["flying_object_drop_degrees"], speed=self.config["flying_object_speed"], brake=self.config["flying_object_brake"]).start(thread=False)
        self.turning_object.move_to(position=self.config["spinning_object_180_degree_turn"], speed=self.config["spinning_object_speed"], brake=self.config["spinning_object_brake"]).start(thread=False)
        

    def insert_actors(self):
        """
        Instructs the user to insert the actors that the play calls for.
        """
        print("\nPlease insert these actors:")
        for actor in self.script["setup"]["actors"]:
            if actor in ['actor_1', 'actor_2']:
                self.move(self.script['setup']['actors'][actor][0], 'stage-center')
            elif actor == 'flying_item':
                self.lower_flying_object()
            elif actor == 'turning_item':
                self.spin_spinning_object()
            print(f"{actor} - {self.script['setup']['actors'][actor][0]}")
        self.stop_motors()
        print("Press C on the theater's screen to confirm that you are done inserting all actors.")
        while not cv2.waitKey(1) & 0xFF == ord('c'):
            time.sleep(.1)
        self.exit_actors()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_valuse, traceback):
        try:
            self.run_window = False
        finally:
            try:
                self.sound.fadeout(1000)
                self.sound.music.fadeout(1000)
                self.stop_motors()
            finally:
                pygame.quit()
                cv2.destroyAllWindows()
        if exc_type is not None:
            logging.error(
                "ERROR",
                exc_info=(exc_type, exc_valuse, traceback)
            )
        return False
        
if __name__ == "__main__":
    BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
    with Robot() as theater:
        theater.load_script(BASE_DIR / "saved_scripts" / "sample_script.json")
        theater.stop_motors()
        theater.start()