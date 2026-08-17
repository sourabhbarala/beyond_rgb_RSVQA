import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
from sympy.codegen.ast import continue_
from xxlimited_35 import Null
import os
# for parsing json output
from langchain_core.output_parsers import JsonOutputParser


import re
from typing import Any
import ast

class accuracy_calculator:
    def __init__(self):
        self.sentinel_path="IGARSS_model_output/sentinel"
        self.landsat_path="IGARSS_model_output/landsat"
        self.lis3_path="IGARSS_model_output/lis3"
        self.lis4_path="IGARSS_model_output/lis4"
      
        self.parent_dirs_path_dict={
            "sentinel":self.sentinel_path,
            "landsat":self.landsat_path,
            "lis3":self.lis3_path,
            "lis4":self.lis4_path
        }
        self.BERT_score_path_dict={
            "original_qwen_with_context":"IGARSS_BERT_scores/original_with_context_BERT_scores.feather",
            "original_qwen_without_context":"IGARSS_BERT_scores/original_without_context_BERT_scores.feather",
            "fine_tuned_qwen_with_context":"IGARSS_BERT_scores/fine_tuned_with_context_BERT_scores.feather",
            "fine_tuned_qwen_without_context":"IGARSS_BERT_scores/fine_tuned_without_context_BERT_scores.feather"}

    
    # def extract_answer(
    #     self,
    #     s: str
    #     ):
    #     try:
    #         data = json.loads(s)
    #         return data.get("answer")
    #     except json.JSONDecodeError:
    #         return None
        
        
    def extract_numeric_answer(
        self,
        model_output: Any):
        """
        Extracts numeric value of `answer` from:
        - ```json { "answer": 1 } ```
        - plain text + JSON block
        - already-parsed dict
        - broken formatting
        Returns int/float or None
        """

        # Case 1: already a dict
        if isinstance(model_output, dict):
            # return model_output.get("answer")
            return model_output

        if not isinstance(model_output, str):
            raise ValueError("model output is not string")

        text = model_output.strip()

        # Case 2: remove code fences ```json ... ```
        text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip("` \n")

        # Case 3: try strict JSON parsing
        try:
            modified_text = text.replace("null", "None")
            val = ast.literal_eval(modified_text)

            if isinstance(val, dict) and "answer" in val:
                return val

        except Exception as e:
            print("ast.literal raising:",e)
            pass


        # Case 4: extract JSON object embedded in text
        json_match = re.search(r"\{[\s\S]*?\}", text)

        if json_match:
            try:
                modified_text = json_match.group().replace("null", "None")

                data = ast.literal_eval(modified_text)

                if "answer" in data:
                    return data

            except json.JSONDecodeError:
                pass
            except SyntaxError as e:
                return False

        # Case 5: regex fallback (last resort)
        num_match = re.search(r'"answer"\s*:\s*(-?\d+(?:\.\d+)?)', text)
        if num_match:
            return {"answer": num_match.group(1)}

        return False
    
    
    def calc_scores(
        self,
        parent_dir_paths_dict:dict
):
        parser=JsonOutputParser()


        def extract_answer(
                s: str
        ):
            try:
                data = json.loads(s)
                return data
            except json.JSONDecodeError:
                return None
            raise ValueError("Could not convert to dictionary.")

        def calc_acc(
                gen_ans,
                ref_ans
        ):
            acc = None
            parsed_gen_ans=None

            if "json" in gen_ans[0].lower():

                try:
                    parsed_gen_ans = parser.parse(gen_ans[0])

                    if 'answer' not in parsed_gen_ans.keys():
                        acc = False

                    else:
                        acc = parsed_gen_ans['answer'].lower() == ref_ans.lower()

                except Exception as e:
                    print(f"Error parsing JSON: {e}")
                    acc = str(ref_ans).lower() in gen_ans[0].lower()

            else:
                acc = str(ref_ans).lower() in gen_ans[0].lower()

            print(f"model ans: {gen_ans} | model parsed ans:{parsed_gen_ans} | ref ans: {ref_ans} | acc:{acc}")
            return acc

        def calc_error(
                gen_ans,
                ref_ans
        ):
            err=None
            parsed_gen_ans=False

            if "json" in gen_ans[0].lower():
                try:
                    parsed_gen_ans = parser.parse(gen_ans[0])

                except Exception as e:
                    print(f"Error parsing JSON: {e}")
                    print("++++++++++++++",end="")
                    parsed_gen_ans = self.extract_numeric_answer(gen_ans[0])

            else:
                print("|||||||||||||||",end="")
                parsed_gen_ans = self.extract_numeric_answer(gen_ans[0])


            if parsed_gen_ans:
                if 'answer' not in parsed_gen_ans.keys():
                    return False
                else:
                    num_parsed_gen_ans = float(parsed_gen_ans['answer']) if parsed_gen_ans['answer'] != None else 0
                    num_ref_ans = float(ref_ans)
                    err= abs(num_ref_ans - num_parsed_gen_ans)

                print(f"model ans: {gen_ans} | model ans:{parsed_gen_ans} | ref ans: {ref_ans} | error:{err}")
                return err

            else: return parsed_gen_ans


        in_sensor_correct_record_dict = {
            "without_context": {},
            "with_context": {}
        }

        error_ques_ans={
            "without_context": {},
            "with_context": {}
        }

        for sensor,parent_dir_path in parent_dir_paths_dict.items():
            print("="*10,sensor,"="*10)
            in_sensor_correct_record_dict["without_context"].setdefault(sensor, {})
            in_sensor_correct_record_dict["with_context"].setdefault(sensor, {})

            bands_dir_names = os.listdir(parent_dir_path)

            for bands_dir_name in bands_dir_names:
                print("-"*10,bands_dir_name,"-"*10)
                in_sensor_correct_record_dict["without_context"][sensor].setdefault(bands_dir_name, {})
                in_sensor_correct_record_dict["with_context"][sensor].setdefault(bands_dir_name, {})

                grounds_truth_file_path= os.path.join(
                    parent_dir_path,
                    bands_dir_name,
                    "generated_answers_v2.json"
                    )

                model_ans_without_context_file_path= os.path.join(
                    parent_dir_path,
                    bands_dir_name,
                    "qwen_output.json"
                    )

                model_ans_with_context_file_path= os.path.join(
                    parent_dir_path,
                    bands_dir_name,
                    "qwen_with_metadata_output.json"
                    )

                ground_truth_json=dict()
                model_ans_without_context_json=dict()
                model_ans_with_context_json=dict()

                with open(grounds_truth_file_path,"r", encoding="utf-8") as f:
                    ground_truth_json=json.load(f)

                with open(model_ans_without_context_file_path,"r", encoding="utf-8") as f:
                    model_ans_without_context_json=json.load(f)

                with open(model_ans_with_context_file_path,"r", encoding="utf-8") as f:
                    model_ans_with_context_json=json.load(f)

                for ques_cat, ques_dict in ground_truth_json.items():

                    if ques_cat in ['object_counting', 'object_area', 'object_localization', 'object_presence', 'attribute_recognition']:

                        print("-"*20,ques_cat,"-"*20)
                        in_sensor_correct_record_dict["without_context"][sensor][bands_dir_name].setdefault(ques_cat,{})
                        in_sensor_correct_record_dict["without_context"][sensor][bands_dir_name][ques_cat]['points_list']=[]

                        in_sensor_correct_record_dict["with_context"][sensor][bands_dir_name].setdefault(ques_cat,{})
                        in_sensor_correct_record_dict["with_context"][sensor][bands_dir_name][ques_cat]['points_list']=[]

                        if ques_cat == "object_counting" or ques_cat == "object_area":
                            for ques,ground_truth in ques_dict.items():
                                print(f"without context error ->",end=" ")
                                error_without_context= calc_error(
                                    gen_ans=model_ans_without_context_json[ques],
                                    ref_ans=ground_truth
                                )

                                print(f"with context error ->",end=" ")
                                error_with_context= calc_error(
                                    gen_ans=model_ans_with_context_json[ques],
                                    ref_ans=ground_truth
                                )
                                if error_without_context==False:
                                    error_ques_ans["without_context"].setdefault(sensor, {})
                                    error_ques_ans["without_context"][sensor].setdefault(bands_dir_name, {})
                                    error_ques_ans["with_context"][sensor][bands_dir_name]={
                                        ques:model_ans_without_context_json[ques],
                                    }
                                else:
                                    in_sensor_correct_record_dict["without_context"][sensor][bands_dir_name][ques_cat]['points_list'].append(error_without_context)

                                if error_with_context==False:
                                    error_ques_ans["with_context"].setdefault(sensor, {})
                                    error_ques_ans["with_context"][sensor].setdefault(bands_dir_name, {})
                                    error_ques_ans["with_context"][sensor][bands_dir_name]={
                                        ques:model_ans_with_context_json[ques],
                                    }
                                else:
                                    in_sensor_correct_record_dict["with_context"][sensor][bands_dir_name][ques_cat]['points_list'].append(error_with_context)

                            print("=================================\n")

                        elif ques_cat in ['object_localization', 'object_presence', 'attribute_recognition']:

                            for ques,ground_truth in ques_dict.items():

                                print(f"without context error ->",end=" ")
                                acc_without_context= calc_acc(
                                    gen_ans=model_ans_without_context_json[ques],
                                    ref_ans=ground_truth
                                )
                                in_sensor_correct_record_dict["without_context"][sensor][bands_dir_name][ques_cat]['points_list'].append(acc_without_context)

                                print(f"with context error ->",end=" ")
                                acc_with_context= calc_acc(
                                    gen_ans=model_ans_with_context_json[ques],
                                    ref_ans=ground_truth
                                )
                                in_sensor_correct_record_dict["with_context"][sensor][bands_dir_name][ques_cat]['points_list'].append(acc_with_context)



                            print("=================================\n")


        def calc_sensor_scores(in_sensor_data):
            sensor_wise_ques_cat_scores_dict={}
            for sensor, in_bands_dir_data in in_sensor_data.items():

                # question category wise avg scores for each bands_dir
                temp_dict={}
                sensor_ques_cat_scores_dict={}



                for bands_dir_name, ques_cat_data in in_bands_dir_data.items():

                    for ques_cat, ques_cat_meta_data in ques_cat_data.items():

                        temp_dict.setdefault(ques_cat, []).append(
                            sum(
                                ques_cat_meta_data['points_list']
                            )/len(ques_cat_meta_data['points_list']) if ques_cat_meta_data['points_list'] else 0
                        )


                for ques_cat, bands_dir_avg_list in temp_dict.items():

                    sensor_ques_cat_scores_dict[ques_cat]=sum(bands_dir_avg_list)/len(bands_dir_avg_list)

                sensor_wise_ques_cat_scores_dict[sensor]=sensor_ques_cat_scores_dict

            return sensor_wise_ques_cat_scores_dict




        sensor_wise_without_context_scores = calc_sensor_scores(in_sensor_correct_record_dict['without_context'])
        sensor_wise_with_context_scores=calc_sensor_scores(in_sensor_correct_record_dict['with_context'])

        return sensor_wise_without_context_scores, sensor_wise_with_context_scores
    
    def covert_to_df(
        self,
        raw_scores):
        rows = []
        for sensor, cat_data in raw_scores.items():
            row = {"sensor": sensor}
            for ques_cat, score in cat_data.items():
                
                if ques_cat == "attribute_recognition":
                    col_name = "attr_rec"
                    row[col_name] = round(score,4)
                    
                elif ques_cat == "object_presence":
                    col_name = "obj_pres"
                    row[col_name] = round(score,4)
                    
                elif ques_cat == "object_localization":
                    col_name = "obj_local"
                    row[col_name] = round(score,4)
                    
                elif ques_cat == "object_counting":
                    col_name = "obj_count"
                    row[col_name] = round(score,4)
                    
                elif ques_cat == "object_area":
                    col_name = "obj_area"
                    row[col_name] = round(score,4)
            rows.append(row)

        # create DataFrame
        df = pd.DataFrame(rows)
        df = df.set_index("sensor")
        return df
                
    def get_accuracy_df(self):
        orig_qwen_without_context_scores, orig_qwen_with_context_scores=self.calc_scores(
            parent_dir_paths_dict=self.parent_dirs_path_dict
        )
        
        orig_qwen_without_context_scores_df = self.covert_to_df(orig_qwen_without_context_scores)
        orig_qwen_with_context_scores_df = self.covert_to_df(orig_qwen_with_context_scores)
        
        ft_qwen_without_context_scores, ft_qwen_with_context_scores=self.calc_scores(
            parent_dir_paths_dict=self.parent_dirs_path_dict
        )
        
        ft_qwen_without_context_scores_df = self.covert_to_df(ft_qwen_without_context_scores)
        ft_qwen_with_context_scores_df = self.covert_to_df(ft_qwen_with_context_scores)
        
        
        orig_qwen_without_context_combined_scores = None
        orig_qwen_with_context_combined_scores = None
        ft_qwen_without_context_combined_scores = None
        ft_qwen_with_context_combined_scores = None
        
        dirs=os.listdir("./")
        
        if "IGARSS_BERT_scores" in dirs:
            files_in_IGARSS_BERT_scores=os.listdir()
            if "original_without_context_BERT_scores.feather" in files_in_IGARSS_BERT_scores:
                
                orig_qwen_without_context_BERT=pd.read_feather(self.BERT_score_path_dict["original_qwen_without_context"])
                
                orig_qwen_without_context_combined_scores=pd.merge(orig_qwen_without_context_scores_df, orig_qwen_without_context_BERT, on="sensor")
                
                orig_qwen_without_context_combined_scores.rename(columns={"image_caption_p":"img_cap_P"}, inplace=True)
                orig_qwen_without_context_combined_scores.rename(columns={"image_caption_r":"img_cap_R"}, inplace=True)
                orig_qwen_without_context_combined_scores.rename(columns={"image_caption_f1":"img_cap_F1"}, inplace=True)
                orig_qwen_without_context_combined_scores.rename(columns={"attribute_reasoning_p":"attr_re_P"}, inplace=True)
                orig_qwen_without_context_combined_scores.rename(columns={"attribute_reasoning_r":"attr_re_R"}, inplace=True)
                orig_qwen_without_context_combined_scores.rename(columns={"attribute_reasoning_f1":"attr_re_F1"}, inplace=True)
                orig_qwen_without_context_combined_scores
                
            if "original_with_context_BERT_scores.feather" in files_in_IGARSS_BERT_scores:
                orig_qwen_with_context_BERT=pd.read_feather(self.BERT_score_path_dict["original_qwen_with_context"])
                
                orig_qwen_with_context_combined_scores=pd.merge(orig_qwen_with_context_scores_df, orig_qwen_with_context_BERT, on="sensor")
                
                orig_qwen_with_context_combined_scores.rename(columns={"image_caption_p":"img_cap_P"}, inplace=True)
                orig_qwen_with_context_combined_scores.rename(columns={"image_caption_r":"img_cap_R"}, inplace=True)
                orig_qwen_with_context_combined_scores.rename(columns={"image_caption_f1":"img_cap_F1"}, inplace=True)
                orig_qwen_with_context_combined_scores.rename(columns={"attribute_reasoning_p":"attr_re_P"}, inplace=True)
                orig_qwen_with_context_combined_scores.rename(columns={"attribute_reasoning_r":"attr_re_R"}, inplace=True)
                orig_qwen_with_context_combined_scores.rename(columns={"attribute_reasoning_f1":"attr_re_F1"}, inplace=True)
                orig_qwen_with_context_combined_scores
                
                
            if "fine_tuned_without_context_BERT_scores.feather" in files_in_IGARSS_BERT_scores:
                ft_qwen_without_context_BERT=pd.read_feather(self.BERT_score_path_dict["fine_tuned_qwen_without_context"])
                ft_qwen_without_context_combined_scores=pd.merge(ft_qwen_without_context_scores_df, ft_qwen_without_context_BERT, on="sensor")
                
                ft_qwen_without_context_combined_scores.rename(columns={"image_caption_p":"img_cap_P"}, inplace=True)
                ft_qwen_without_context_combined_scores.rename(columns={"image_caption_r":"img_cap_R"}, inplace=True)
                ft_qwen_without_context_combined_scores.rename(columns={"image_caption_f1":"img_cap_F1"}, inplace=True)
                ft_qwen_without_context_combined_scores.rename(columns={"attribute_reasoning_p":"attr_re_P"}, inplace=True)
                ft_qwen_without_context_combined_scores.rename(columns={"attribute_reasoning_r":"attr_re_R"}, inplace=True)
                ft_qwen_without_context_combined_scores.rename(columns={"attribute_reasoning_f1":"attr_re_F1"}, inplace=True)
                ft_qwen_without_context_combined_scores
                
                
            if "fine_tuned_with_context_BERT_scores.feather" in files_in_IGARSS_BERT_scores:
        
                ft_qwen_with_context_BERT=pd.read_feather(self.BERT_score_path_dict["fine_tuned_qwen_with_context"])
                ft_qwen_with_context_combined_scores=pd.merge(ft_qwen_with_context_scores_df, ft_qwen_with_context_BERT, on="sensor")

                ft_qwen_with_context_combined_scores.rename(columns={"image_caption_p":"img_cap_P"}, inplace=True)
                ft_qwen_with_context_combined_scores.rename(columns={"image_caption_r":"img_cap_R"}, inplace=True)
                ft_qwen_with_context_combined_scores.rename(columns={"image_caption_f1":"img_cap_F1"}, inplace=True)
                ft_qwen_with_context_combined_scores.rename(columns={"attribute_reasoning_p":"attr_re_P"}, inplace=True)
                ft_qwen_with_context_combined_scores.rename(columns={"attribute_reasoning_r":"attr_re_R"}, inplace=True)
                ft_qwen_with_context_combined_scores.rename(columns={"attribute_reasoning_f1":"attr_re_F1"}, inplace=True)
                ft_qwen_with_context_combined_scores
        
        score_dict= {
            "original_qwen_without_context_scores": orig_qwen_without_context_scores_df if orig_qwen_without_context_combined_scores is None else orig_qwen_without_context_combined_scores,
            "original_qwen_with_context_scores":orig_qwen_with_context_scores_df if orig_qwen_with_context_combined_scores is None else orig_qwen_with_context_combined_scores,
            "fine_tuned_qwen_without_context_scores":ft_qwen_without_context_scores_df if ft_qwen_without_context_combined_scores is None else ft_qwen_without_context_combined_scores,
            "fine_tuned_qwen_with_context_scores":ft_qwen_with_context_scores_df if ft_qwen_with_context_combined_scores is None else ft_qwen_with_context_combined_scores}
        
        return score_dict
        
            
    def save_accuracy_df(self):
        path_to_scores="./IGARSS_scores"
        
        os.makedirs(path_to_scores, exist_ok=True)
        score_dict=self.get_accuracy_df()
        score_dict["original_qwen_without_context_scores"].to_csv(os.path.join(path_to_scores,"original_qwen_without_context.csv"))
        score_dict["original_qwen_with_context_scores"].to_csv(os.path.join(path_to_scores,"original_qwen_with_context.csv"))
        score_dict["fine_tuned_qwen_without_context_scores"].to_csv(os.path.join(path_to_scores,"fine_tuned_qwen_without_context.csv"))
        score_dict["fine_tuned_qwen_with_context_scores"].to_csv(os.path.join(path_to_scores,"fine_tuned_qwen_with_context.csv"))
