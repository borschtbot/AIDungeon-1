import json
import os
import warnings

import numpy as np
import tensorflow as tf
from generator.gpt2.src import encoder, model, sample
from story.utils import *

warnings.filterwarnings("ignore")

tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)


class GPT2Generator:
    def __init__(self, generate_num=80, temperature=0.1, top_k=30, top_p=0.9, censor=False):
        self.generate_num = generate_num
        self.default_gen_num = generate_num
        self.temp = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.censor = censor

        self.model_name = "model_v5"
        self.model_dir = "generator/gpt2/models"
        self.checkpoint_path = os.path.join(self.model_dir, self.model_name)

        self.batch_size = 1
        self.samples = 1

        models_dir = os.path.expanduser(os.path.expandvars(self.model_dir))
        self.enc = encoder.get_encoder(self.model_name, models_dir)

        config = tf.compat.v1.ConfigProto()
        config.gpu_options.allow_growth = True
        self.sess = tf.compat.v1.Session(config=config)

        self.context = tf.placeholder(tf.int32, [self.batch_size, None])
        # np.random.seed(seed)
        # tf.set_random_seed(seed)
        self.gen_output()

        saver = tf.train.Saver()
        ckpt = tf.train.latest_checkpoint(os.path.join(models_dir, self.model_name))
        saver.restore(self.sess, ckpt)

    def prompt_replace(self, prompt):
        # print("\n\nBEFORE PROMPT_REPLACE:")
        # print(repr(prompt))
        if len(prompt) > 0 and prompt[-1] == " ":
            prompt = prompt[:-1]

        # prompt = second_to_first_person(prompt)

        # print("\n\nAFTER PROMPT_REPLACE")
        # print(repr(prompt))
        return prompt

    def result_replace(self, result):
        # print("\n\nBEFORE RESULT_REPLACE:")
        # print(repr(result))

        result = cut_trailing_sentence(result)
        if len(result) == 0:
            return ""
        first_letter_capitalized = result[0].isupper()
        result = result.replace('."', '".')
        result = result.replace("#", "")
        result = result.replace("*", "")
        result = result.replace("\n\n", "\n")
        # result = first_to_second_person(result)
        if self.censor:
            result = remove_profanity(result)

        if not first_letter_capitalized:
            result = result[0].lower() + result[1:]

        #
        # print("\n\nAFTER RESULT_REPLACE:")
        # print(repr(result))

        return result

    def generate_raw(self, prompt):
        while len(prompt) > 3500:
            prompt = self.cut_down_prompt(prompt)
        context_tokens = self.enc.encode(prompt)
        generated = 0
        for _ in range(self.samples // self.batch_size):
            out = self.sess.run(
                self.output,
                feed_dict={
                    self.context: [context_tokens for _ in range(self.batch_size)]
                },
            )[:, len(context_tokens) :]
            for i in range(self.batch_size):
                generated += 1
                text = self.enc.decode(out[i])
        return text

    def generate(self, prompt, options=None, seed=1, depth=1):

        debug_print = False
        prompt = self.prompt_replace(prompt)

        if debug_print:
            print("******DEBUG******")
            print("Prompt is: ", repr(prompt))

        text = self.generate_raw(prompt)

        if debug_print:
            print("Generated result is: ", repr(text))
            print("******END DEBUG******")

        result = text
        result = self.result_replace(result)
        if len(result) == 0 and depth < 20:
            return self.generate(self.cut_down_prompt(prompt), depth=depth+1)

        return result
        
    def cut_down_prompt(self, prompt):
        split_prompt = prompt.split(">")
        expendable_text = ">".join(split_prompt[2:])
        return split_prompt[0] + ">" + expendable_text
        
    def gen_output(self):
        models_dir = os.path.expanduser(os.path.expandvars(self.model_dir))
        hparams = model.default_hparams()
        with open(os.path.join(models_dir, self.model_name, "hparams.json")) as f:
            hparams.override_from_dict(json.load(f))
        seed = np.random.randint(0, 100000)
        self.output = sample.sample_sequence(
            hparams=hparams,
            length=self.generate_num,
            context=self.context,
            batch_size=self.batch_size,
            temperature=self.temp,
            top_k=self.top_k,
            top_p=self.top_p,
        )
        
    def change_temp(self, t):
        self.temp = t
        self.gen_output()
        
    def change_topk(self, t):
        self.top_k = t
        self.gen_output()
