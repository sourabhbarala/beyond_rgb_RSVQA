import os
import json
from typing import Literal, Union

class TestQuestions:
    def __init__(self):
        self.default_output_parent_dir = "./DSAA_questions"
        self.question_category_alias_names={
            "vegetation":["vegetation","veg","vegetation_coverage","vegetation_coverage_info"],
            "water":["water","water_bodies","water_bodies_info"],
            "built_up":["built_up","built","built_up_coverage","built_up_coverage_info"],
        }
    
    def get_water_questions(
        self
    ):
        water_questions = {
            "bigger_than_area": [
                {
                    "question":"What is the average area of water bodies having an area greater than {bigger_than_water_threshold} square meters?",
                    "sql_command":"SELECT AVG(water_body_area_m2) FROM water_bodies_info_table WHERE water_body_area_m2 > {bigger_than_water_threshold};"},
                {
                    "question":"What is the location of the smallest water body among those having an area greater than {bigger_than_water_threshold} square meters?",
                    "sql_command":"""\
                        SELECT bounding_box_or_location FROM water_bodies_info_table 
            WHERE water_body_area_m2 = (
                SELECT MIN(water_body_area_m2) FROM water_bodies_info_table 
                WHERE water_body_area_m2 > {bigger_than_water_threshold}
            );"""},
                {
                    "question":"What percentage of the total water area is covered by water bodies having an area greater than {bigger_than_water_threshold} square meters?",
                    "sql_command":"""SELECT (SUM(CASE WHEN water_body_area_m2 > {bigger_than_water_threshold} THEN water_body_area_m2 ELSE 0 END) * 100.0 
            / SUM(water_body_area_m2)) FROM water_bodies_info_table;"""},
                {
                    "question":"List the locations of water bodies having an area greater than {bigger_than_water_threshold} square meters.",
                    "sql_command":"""SELECT bounding_box_or_location FROM water_bodies_info_table 
            WHERE water_body_area_m2 > {bigger_than_water_threshold};"""},
            ],
            
            "smaller_than_area": [
                {
                    "question":"How many water bodies have an area smaller than {smaller_than_water_threshold} square meters?",
                    "sql_command":"SELECT COUNT(*) FROM water_bodies_info_table WHERE water_body_area_m2 < {smaller_than_water_threshold};"},
                {
                    "question":"What is the area of the biggest water body among those having an area smaller than {smaller_than_water_threshold} square meters?",
                    "sql_command":"SELECT MAX(water_body_area_m2) FROM water_bodies_info_table WHERE water_body_area_m2 < {smaller_than_water_threshold};"},
                {
                    "question":"What is the total area covered by water bodies having an area smaller than {smaller_than_water_threshold} square meters?",
                    "sql_command":"SELECT SUM(water_body_area_m2) FROM water_bodies_info_table WHERE water_body_area_m2 < {smaller_than_water_threshold};"},
                {
                    "question":"List the areas of water bodies having an area smaller than {smaller_than_water_threshold} square meters.",
                    "sql_command":"""SELECT water_body_area_m2 FROM water_bodies_info_table 
            WHERE water_body_area_m2 < {smaller_than_water_threshold};"""},
            ],
            
            "between_area": [
                {
                    "question": "How many water bodies have an area above {between_water_lower_threshold} square meters and below {between_water_upper_threshold} square meters?",
                    "sql_command": "SELECT COUNT(*) FROM water_bodies_info_table WHERE water_body_area_m2 > {between_water_lower_threshold} AND water_body_area_m2 < {between_water_upper_threshold};"},
                {
                    "question": "What is the average area of water bodies having an area above {between_water_lower_threshold} square meters and below {between_water_upper_threshold} square meters?",
                    "sql_command": "SELECT AVG(water_body_area_m2) FROM water_bodies_info_table WHERE water_body_area_m2 > {between_water_lower_threshold} AND water_body_area_m2 < {between_water_upper_threshold};"},
                {
                    "question": "What is the total area covered by water bodies having an area above {between_water_lower_threshold} square meters and below {between_water_upper_threshold} square meters?",
                    "sql_command": "SELECT SUM(water_body_area_m2) FROM water_bodies_info_table WHERE water_body_area_m2 > {between_water_lower_threshold} AND water_body_area_m2 < {between_water_upper_threshold};"},
                {
                    "question": "What percentage of the total water area is covered by water bodies having an area above {between_water_lower_threshold} square meters and below {between_water_upper_threshold} square meters?",
                    "sql_command": """SELECT (SUM(CASE WHEN water_body_area_m2 > {between_water_lower_threshold} AND water_body_area_m2 < {between_water_upper_threshold} THEN water_body_area_m2 ELSE 0 END) * 100.0 
                / SUM(water_body_area_m2)) FROM water_bodies_info_table;"""},
                {
                    "question": "List the areas of water bodies having an area above {between_water_lower_threshold} square meters and below {between_water_upper_threshold} square meters.",
                    "sql_command": """SELECT water_body_area_m2 FROM water_bodies_info_table 
                WHERE water_body_area_m2 > {between_water_lower_threshold} AND water_body_area_m2 < {between_water_upper_threshold};"""},
                {
                    "question": "List the locations of water bodies having an area above {between_water_lower_threshold} square meters and below {between_water_upper_threshold} square meters.",
                    "sql_command": """SELECT bounding_box_or_location FROM water_bodies_info_table 
                WHERE water_body_area_m2 > {between_water_lower_threshold} AND water_body_area_m2 < {between_water_upper_threshold};"""},
            ],

            "top_n": [
                {
                    "question":"What is the total area covered by the top {top_n_water_bodies} largest water bodies?",
                    "sql_command":"""SELECT SUM(water_body_area_m2) FROM (
                SELECT water_body_area_m2 FROM water_bodies_info_table 
                ORDER BY water_body_area_m2 DESC LIMIT {top_n_water_bodies}
            );"""},
                {
                    "question":"List the areas of the top {top_n_water_bodies} largest water bodies.",
                    "sql_command":"""SELECT water_body_area_m2 FROM water_bodies_info_table ORDER BY water_body_area_m2 DESC LIMIT {top_n_water_bodies};"""},
            ],
            
            "bottom_n": [
                {
                    "question":"What is the average area of the bottom {bottom_n_water_bodies} smallest water bodies?",
                    "sql_command":"""SELECT AVG(water_body_area_m2) FROM (
                SELECT water_body_area_m2 FROM water_bodies_info_table 
                ORDER BY water_body_area_m2 ASC LIMIT {bottom_n_water_bodies}
            );"""},
                {
                    "question":"What percentage of the total water area is covered by the bottom {bottom_n_water_bodies} smallest water bodies?",
                    "sql_command":"""SELECT (
            (SELECT SUM(water_body_area_m2) FROM (
                SELECT water_body_area_m2 FROM water_bodies_info_table 
                ORDER BY water_body_area_m2 ASC LIMIT {bottom_n_water_bodies}
            )) 
            * 100.0 / 
            (SELECT SUM(water_body_area_m2) FROM water_bodies_info_table));"""},
                {
                    "question":"List the locations of the bottom {bottom_n_water_bodies} smallest water bodies.",
                    "sql_command":"""SELECT bounding_box_or_location FROM water_bodies_info_table 
            ORDER BY water_body_area_m2 ASC LIMIT {bottom_n_water_bodies};"""},
            ],
            
            "no_filter": [
                {
                    "question":"What is the area of the fourth smallest water body in square kilometers?",
                    "sql_command":"SELECT water_body_area_m2/1000000 FROM water_bodies_info_table ORDER BY water_body_area_m2 ASC LIMIT 1 OFFSET 3;"},
                {
                    "question":"What is the location of the third biggest water body?",
                    "sql_command":"SELECT bounding_box_or_location FROM water_bodies_info_table ORDER BY water_body_area_m2 DESC LIMIT 1 OFFSET 2;"},
                {
                    "question":"How much do the water body areas differ from their average area?",
                    "sql_command":"""SELECT SQRT(AVG(water_body_area_m2 * water_body_area_m2) - AVG(water_body_area_m2) * AVG(water_body_area_m2)) 
            FROM water_bodies_info_table;"""},
            ],
            
            "ratio": [
                {
                    "question":"What is the ratio of the area of the biggest water body to the area of the smallest water body?",
                    "sql_command":"""SELECT CAST(MAX(water_body_area_m2) AS FLOAT) / MIN(water_body_area_m2) 
            FROM water_bodies_info_table;"""},
                {
                    "question":"What percentage of the total water area is covered by the biggest water body?",
                    "sql_command":"""SELECT (MAX(water_body_area_m2) * 100.0 / SUM(water_body_area_m2)) 
            FROM water_bodies_info_table;"""},
            ],
        }
        return water_questions
    
    def get_vegetation_questions(
        self):
        vegetation_questions = {
            "bigger_than_area": [
                {
                    "question": "What is the average total vegetation coverage among regions having a total vegetation coverage greater than {bigger_than_veg_cover_threshold} square kilometers (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"SELECT AVG(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) FROM vegetation_coverage_info_table WHERE (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) > {bigger_than_veg_cover_threshold};"},
                {
                    "question": "What percentage of the combined vegetation coverage across all regions is contributed by regions whose total vegetation coverage exceeds {bigger_than_veg_cover_threshold} square kilometers (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"""SELECT (SUM(CASE WHEN (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) > {bigger_than_veg_cover_threshold} THEN (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) ELSE 0 END) * 100.0 
            / SUM(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2)) FROM vegetation_coverage_info_table;"""},
            ],
            
            "smaller_than_area": [
                {
                    "question": "How many regions of the image have a total vegetation coverage less than {smaller_than_veg_cover_threshold} square kilometers (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"SELECT COUNT(*) FROM vegetation_coverage_info_table WHERE (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) < {smaller_than_veg_cover_threshold};"},
                {
                    "question": "What is the total vegetation coverage area among regions having a vegetation coverage less than {smaller_than_veg_cover_threshold} square kilometers (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"SELECT SUM(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) FROM vegetation_coverage_info_table WHERE (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) < {smaller_than_veg_cover_threshold};"},
            ],
            
            "between_area": [
                {
                    "question": "What is the average vegetation coverage among regions having a vegetation coverage above {between_veg_cover_lower_threshold} square kilometers and below {between_veg_cover_upper_threshold} square kilometers (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command": "SELECT AVG(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) FROM vegetation_coverage_info_table WHERE (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) > {between_veg_cover_lower_threshold} AND (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) < {between_veg_cover_upper_threshold};"
                },
                {
                    "question": "What percentage of the combined vegetation coverage across all regions is contributed by regions whose total vegetation coverage is above {between_veg_cover_lower_threshold} square kilometers and below {between_veg_cover_upper_threshold} square kilometers (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command": """SELECT (SUM(CASE WHEN (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) > {between_veg_cover_lower_threshold} AND (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) < {between_veg_cover_upper_threshold} THEN (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) ELSE 0 END) * 100.0
            / SUM(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2)) FROM vegetation_coverage_info_table;"""},
            {
                "question": "Which regions of the image have a vegetation coverage above {between_veg_cover_lower_threshold} square kilometers and below {between_veg_cover_upper_threshold} square kilometers (note: total vegetation = sparse + moderate + dense vegetation)?",
                "sql_command": """SELECT cell_name FROM vegetation_coverage_info_table 
            WHERE (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) > {between_veg_cover_lower_threshold} AND (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) < {between_veg_cover_upper_threshold};"""}
            ],
            
            "top_n": [
                {
                    "question": "List the total vegetation coverage areas of the top {top_n_veg_cover} regions with the highest vegetation coverage (note: total vegetation = sparse + moderate + dense vegetation).",
                    "sql_command":"""SELECT cell_name, (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) AS total_vegetation_km2 
            FROM vegetation_coverage_info_table 
            ORDER BY total_vegetation_km2 DESC LIMIT {top_n_veg_cover};"""},
            ],
            
            "bottom_n": [
                {   
                    "question": "What is the average total vegetation coverage area of the bottom {bottom_n_veg_cover} regions with the least vegetation coverage (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"""SELECT AVG(veg) FROM (
                SELECT (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) AS veg FROM vegetation_coverage_info_table 
                ORDER BY (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) ASC LIMIT {bottom_n_veg_cover}
            );"""},
                {
                    "question": "What percentage of the combined vegetation coverage across all regions is contributed by the bottom {bottom_n_veg_cover} regions with the least vegetation coverage (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"""SELECT (
                (SELECT SUM(veg) FROM (
                    SELECT (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) AS veg 
                    FROM vegetation_coverage_info_table 
                    ORDER BY veg ASC LIMIT {bottom_n_veg_cover}
                ))
                * 100.0 /
                (SELECT SUM(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) 
                FROM vegetation_coverage_info_table)
            );"""},
            ],
            
            "particular_location": [
                {
                    "question": "What is the average total vegetation coverage across the upper left, center, and lower right regions of the image (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"""SELECT AVG(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2)
            FROM vegetation_coverage_info_table
            WHERE cell_name IN ('upper left', 'center', 'lower right');"""},
                {
                    "question": "Which region among the upper right, center, and lower left has the highest total vegetation coverage (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"""SELECT cell_name FROM vegetation_coverage_info_table
            WHERE cell_name IN ('upper right', 'center', 'lower left')
            ORDER BY (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) DESC
            LIMIT 1;"""},
                {
                    "question": "What percentage of the combined vegetation coverage across all regions is contributed by the upper left, upper middle, and upper right regions of the image (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"""SELECT (SUM(CASE WHEN cell_name IN ('upper left', 'upper middle', 'upper right') 
                    THEN (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) ELSE 0 END) * 100.0
            / SUM(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2))
            FROM vegetation_coverage_info_table;"""},
            ],
            
            "no_filter": [
                {
                    "question": "What is the total vegetation coverage of the region with the third highest vegetation coverage (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"""SELECT (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) AS total_vegetation_km2 FROM vegetation_coverage_info_table 
            ORDER BY (sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) DESC LIMIT 1 OFFSET 2;"""},
                {
                    "question": "What is the average dense vegetation coverage across all regions?",
                    "sql_command":"SELECT AVG(dense_vegetation_area_km2) FROM vegetation_coverage_info_table;"},
                {
                    "question": "Which region has the lowest sparse vegetation coverage?",
                    "sql_command":"""SELECT cell_name FROM vegetation_coverage_info_table 
            ORDER BY sparse_vegetation_area_km2 ASC LIMIT 1;"""},
                {
                    "question": "Which region has the most scattered or discontinuous vegetation cover?",
                    "sql_command": """SELECT cell_name FROM vegetation_coverage_info_table 
                WHERE morans_i_p_value < 0.05 
                ORDER BY morans_i_index ASC LIMIT 1;"""},
                {
                    "question": "Which region has the most homogeneous or clustered vegetation cover?",
                    "sql_command": """SELECT cell_name FROM vegetation_coverage_info_table 
                WHERE morans_i_p_value < 0.05 
                ORDER BY morans_i_index DESC LIMIT 1;"""}
            ],
            
            "ratio": [
                {
                    "question": "What is the ratio of the total vegetation coverage of the region with the highest total vegetation coverage to that of the region with the lowest total vegetation coverage (note: total vegetation = sparse + moderate + dense vegetation)?",
                    "sql_command":"""SELECT CAST(MAX(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) AS FLOAT) / MIN(sparse_vegetation_area_km2 + moderate_vegetation_area_km2 + dense_vegetation_area_km2) 
            FROM vegetation_coverage_info_table;"""},
            ],
        }
        
        return vegetation_questions
    
    def get_built_up_questions(
        self):
        built_up_questions = {
            "bigger_than_area": [
                {
                    "question": "Which region has the least total built-up coverage among regions having a built-up coverage greater than {bigger_than_built_cover_threshold} square kilometers (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"""SELECT cell_name FROM built_up_coverage_info_table 
            WHERE (medium_density_built_up_area_km2 + high_density_built_up_area_km2) = (
                SELECT MIN(medium_density_built_up_area_km2 + high_density_built_up_area_km2) FROM built_up_coverage_info_table 
                WHERE (medium_density_built_up_area_km2 + high_density_built_up_area_km2) > {bigger_than_built_cover_threshold}
            );"""},
                {
                    "question": "Which regions of the image have a total built-up coverage greater than {bigger_than_built_cover_threshold} square kilometers (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"""SELECT cell_name FROM built_up_coverage_info_table 
            WHERE (medium_density_built_up_area_km2 + high_density_built_up_area_km2) > {bigger_than_built_cover_threshold};"""},
            ],
            
            "smaller_than_area": [
                {
                    "question": "What is the maximum total built-up coverage among regions having a built-up coverage less than {smaller_than_built_cover_threshold} square kilometers (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"SELECT MAX(medium_density_built_up_area_km2 + high_density_built_up_area_km2) FROM built_up_coverage_info_table WHERE (medium_density_built_up_area_km2 + high_density_built_up_area_km2) < {smaller_than_built_cover_threshold};"},
                {
                    "question": "List the total built-up coverage areas of regions having a total built-up coverage less than {smaller_than_built_cover_threshold} square kilometers (note: total built-up = medium density + high density built-up).",
                    "sql_command":"""SELECT (medium_density_built_up_area_km2 + high_density_built_up_area_km2) AS total_built_up_km2 FROM built_up_coverage_info_table 
            WHERE (medium_density_built_up_area_km2 + high_density_built_up_area_km2) < {smaller_than_built_cover_threshold}
            ORDER BY total_built_up_km2 ASC;"""},
            ],
            
            "between_area": [
                {
                    "question": "How many regions of the image have a total built-up coverage above {between_built_cover_lower_threshold} square kilometers and below {between_built_cover_upper_threshold} square kilometers (note: total built-up = medium density + high density built-up)?",
                    "sql_command": "SELECT COUNT(*) FROM built_up_coverage_info_table WHERE (Medium_density_built_up_area_km2 + High_density_built_up_area_km2) > {between_built_cover_lower_threshold} AND (Medium_density_built_up_area_km2 + High_density_built_up_area_km2) < {between_built_cover_upper_threshold};"},
                {
                    "question": "What is the total built-up coverage area among regions having a built-up coverage above {between_built_cover_lower_threshold} square kilometers and below {between_built_cover_upper_threshold} square kilometers (note: total built-up = medium density + high density built-up)?",
                    "sql_command": "SELECT SUM(Medium_density_built_up_area_km2 + High_density_built_up_area_km2) FROM built_up_coverage_info_table WHERE (Medium_density_built_up_area_km2 + High_density_built_up_area_km2) > {between_built_cover_lower_threshold} AND (Medium_density_built_up_area_km2 + High_density_built_up_area_km2) < {between_built_cover_upper_threshold};"},
                {
                    "question": "List the total built-up coverage areas of regions having a built-up coverage above {between_built_cover_lower_threshold} square kilometers and below {between_built_cover_upper_threshold} square kilometers in descending order (note: total built-up = medium density + high density built-up).",
                    "sql_command": """SELECT cell_name, (Medium_density_built_up_area_km2 + High_density_built_up_area_km2) AS total_built_up_km2 FROM built_up_coverage_info_table 
            WHERE (Medium_density_built_up_area_km2 + High_density_built_up_area_km2) > {between_built_cover_lower_threshold} AND (Medium_density_built_up_area_km2 + High_density_built_up_area_km2) < {between_built_cover_upper_threshold}
            ORDER BY total_built_up_km2 DESC;"""},
            ],
            
            "top_n": [
                {
                    "question": "What is the total built-up coverage area of the top {top_n_built_cover} regions with the highest total built-up coverage (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"""SELECT SUM(built) FROM (
                SELECT (medium_density_built_up_area_km2 + high_density_built_up_area_km2) AS built FROM built_up_coverage_info_table 
                ORDER BY (medium_density_built_up_area_km2 + high_density_built_up_area_km2) DESC LIMIT {top_n_built_cover}
            );"""},
            ],
            
            "bottom_n": [
                {
                    "question": "Which are the bottom {bottom_n_built_cover} regions with the least total built-up coverage (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"""SELECT cell_name FROM built_up_coverage_info_table 
            ORDER BY (medium_density_built_up_area_km2 + high_density_built_up_area_km2) ASC LIMIT {bottom_n_built_cover};"""},
            ],
            
            "particular_location": [
                {
                    "question": "What is the lowest total built-up coverage area among the upper middle, center, and lower middle regions of the image (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"""SELECT MIN(medium_density_built_up_area_km2 + high_density_built_up_area_km2)
            FROM built_up_coverage_info_table
            WHERE cell_name IN ('upper middle', 'center', 'lower middle');"""},
                {
                    "question": "What is the total built-up coverage area of the upper left, middle left, and lower left regions of the image (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"""SELECT SUM(medium_density_built_up_area_km2 + high_density_built_up_area_km2)
            FROM built_up_coverage_info_table
            WHERE cell_name IN ('upper left', 'middle left', 'lower left');"""},
                {
                    "question": "List the total built-up coverage areas of the upper left, upper right, middle left, middle right, lower left, and lower right regions in descending order (note: total built-up = medium density + high density built-up).",
                    "sql_command":"""SELECT cell_name, (medium_density_built_up_area_km2 + high_density_built_up_area_km2) AS total_built_up_km2
            FROM built_up_coverage_info_table
            WHERE cell_name IN ('upper left', 'upper right', 'middle left', 'middle right', 'lower left', 'lower right')
            ORDER BY total_built_up_km2 DESC;"""},
            ],
            
            "no_filter": [
                {
                    "question": "Which region has the third lowest total built-up coverage (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"""SELECT cell_name FROM built_up_coverage_info_table 
            ORDER BY (medium_density_built_up_area_km2 + high_density_built_up_area_km2) ASC LIMIT 1 OFFSET 2;"""},
                {
                    "question": "Which region has the lowest high density built-up?",
                    "sql_command":"""SELECT cell_name FROM built_up_coverage_info_table 
            ORDER BY high_density_built_up_area_km2 ASC LIMIT 1;"""},
                {
                    "question": "What is the high density built-up coverage area of the region with the highest total built-up coverage (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"SELECT high_density_built_up_area_km2 FROM built_up_coverage_info_table ORDER BY (medium_density_built_up_area_km2 + high_density_built_up_area_km2) DESC LIMIT 1;"},
            ],
            
            "ratio": [
            {
                    "question": "What is the ratio of high density built-up cover to total built-up coverage for each region of the image (note: total built-up = medium density + high density built-up)?",
                    "sql_command":"""SELECT cell_name, 
                    CAST(high_density_built_up_area_km2 AS FLOAT) / (medium_density_built_up_area_km2 + high_density_built_up_area_km2) AS high_density_to_total_ratio 
                    FROM built_up_coverage_info_table 
                    ORDER BY high_density_to_total_ratio DESC;"""}
            ],
        }
        
        return built_up_questions
    
    def get_questions_for_category(
        self,
        questions_category:Literal["vegetation","veg","vegetation_coverage","vegetation_coverage_info","water","water_bodies","water_bodies_info","built_up","built","built_up_coverage","built_up_coverage_info"]):
        
        if questions_category in self.question_category_alias_names["vegetation"]:
            return self.get_vegetation_questions()
        elif questions_category in self.question_category_alias_names["water"]:
            return self.get_water_questions()
        elif questions_category in self.question_category_alias_names["built_up"]:
            return self.get_built_up_questions()
        else:
            raise ValueError("Invalid question category")
        
    def save_water_ques_as_json(
        self,
        file_path:str="default_path"
        ):
        if file_path == "default_path":
            file_path = os.path.join(self.default_output_parent_dir, "water_related_questions.json")

        os.makedirs(file_path, exist_ok=True)
        water_questions = self.get_water_questions()
        with open(file_path, 'w') as f:
            json.dump(water_questions, f, indent=4)
            
    def save_vegetation_ques_as_json(
        self,
        file_path:str="default_path"
        ):
        if file_path == "default_path":
            file_path = os.path.join(self.default_output_parent_dir, "vegetation_related_questions.json")

        os.makedirs(file_path, exist_ok=True)
        vegetation_questions = self.get_vegetation_questions()
        with open(file_path, 'w') as f:
            json.dump(vegetation_questions, f, indent=4)
            
    def save_built_up_ques_as_json(
        self,
        file_path:str="default_path"
        ):
        if file_path == "default_path":
            file_path = os.path.join(self.default_output_parent_dir, "built_up_related_questions.json")

        os.makedirs(file_path, exist_ok=True)
        built_up_questions = self.get_built_up_questions()
        with open(file_path, 'w') as f:
            json.dump(built_up_questions, f, indent=4)
            
    def save_all_ques_as_json(
        self,
        file_path:str="default_path"
        ):
        self.save_water_ques_as_json(file_path)
        self.save_vegetation_ques_as_json(file_path)
        self.save_built_up_ques_as_json(file_path)