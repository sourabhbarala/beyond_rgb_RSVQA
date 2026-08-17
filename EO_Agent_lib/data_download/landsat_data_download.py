import os
import ee
import geemap

class landsat_data_downloader:
    def __init__(
        self,
        gg_project_id:str
        ):

        ee.Authenticate()
        ee.Initialize(project=gg_project_id)

    def make_corners(
        self,
        bbox
        ):
        if type(bbox)==str:
            bbox=[float(coord) for coord in bbox.split(',')]
        lons=[bbox[0],bbox[2]]
        lats=[bbox[1],bbox[3]]
        lons.sort()
        lats.sort()
        corners=[]
        for lon in lons:
            for lat in lats:
                corners.append([lon,lat])
            lats.sort(reverse=True)
        corners.append(corners[0])
        return corners

    def download_band(
        self,
        # corners,
        bbox,
        output_path:str="",
        start_date="",
        end_date="",
        band:str=None,
        
        ):
        """
        Download Landsat 8 tif image for a given AOI defined by 4 corner coordinates.
        corners: List of 4 [lon, lat] pairs, e.g. [[lon1, lat1], [lon2, lat2], [lon3, lat3], [lon4, lat4]]
        filename: Output file path
        start_date, end_date: Date range for image collection
        """
        
        if band is None:
            raise ValueError('Please pass the band!')
        
        bands = [band]
        
        # * google earth engine takes corner coordinates
        corners=self.make_corners(bbox)
        
        #* Ensure the polygon is closed
        if corners[0] != corners[-1]:
            coords = corners + [corners[0]]
        else:
            coords = corners
        aoi = ee.Geometry.Polygon([coords])

        collection = ee.ImageCollection("LANDSAT/LC09/C02/T1_TOA") \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUD_COVER', 10))
        
        image = collection.first().clip(aoi)
        
        selected_bands = image.select(bands)
        if output_path=="":
            
            # * make folder name
            bbox_str=",".join([str(i) for i in bbox])
            
            folder_name = f"{bbox_str}"
            
            if start_date!="":
                folder_name = folder_name + f"_{start_date}"
                
            if end_date!="":
                folder_name = folder_name + f"_to_{end_date}"
                
            # * make file name
            file_name = f"{folder_name}_{band}.tif"
                
            # * make final output path
            output_folder = f"./downloaded_images/landsat9/{folder_name}"
            os.makedirs(output_folder, exist_ok=True)
            output_path = os.path.join(output_folder, f"{file_name}")
            
            
        print(f"Image saved to {output_path}")
        geemap.ee_export_image(
            ee_object=selected_bands,
            filename=output_path,
            region=aoi,
            scale=30,
            file_per_band=True
        )
        