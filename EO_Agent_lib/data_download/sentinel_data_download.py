from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from PIL import Image
import io
import numpy as np
import matplotlib.pyplot as plt

class sentinel_data_downloader:
    def __init__(
        self,
        CLIENT_ID:str,
        CLIENT_SECRET:str
        ):
        
        
        # * set up credentials
        client = BackendApplicationClient(client_id=CLIENT_ID)
        self.oauth = OAuth2Session(client=client)
        
        # * get an authentication token
        self.token = self.oauth.fetch_token(
            token_url='https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token',
            client_secret=CLIENT_SECRET,
            include_client_id=True
        )
        
        
    def fetch_image(
        self,
        bbox,
        band:str,
        start_date,
        end_date,
        resolution_m: int = 10,
        collection_id = "sentinel-2-l2a"
        ):
        
        import numpy as np
        from PIL import Image
        import io
        
        
        print(band)
        
        # * evalscript
        evalscript = """

        function setup() {
        return {
            input: ["""+'"'+band+'"'+"""],
            output: { id: 'default',
                    bands: 1 }
        };
        }

        function evaluatePixel(sample) {
        return [sample."""+band+"""];
        }
        """
        

        # request body/payload
        json_request = {
            'input': {
                'bounds': {
                    'bbox': bbox,
                    'properties': {
                        'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
                    }
                },
                'data': [
                    {
                        'type': 'S2L2A',
                        'dataFilter': {
                            'timeRange': {
                                'from': f'{start_date}T17:00:00Z',
                                'to': f'{end_date}T00:59:59Z'
                            },
                            'mosaickingOrder': 'leastCC',
                        },
                    }
                ]
            },
            'output': {
                'width': 2500,
                'height': 2500,
                'responses': [
                    {
                        'identifier': 'default',
                        'format': {
                            'type': 'image/tiff',
                        }
                    }
                ]
            },
            'evalscript': evalscript
        }



        # * Set the request URL and headers
        url_request = "https://sh.dataspace.copernicus.eu/api/v1/process"
        headers_request = {
            "Authorization": f"Bearer {self.token['access_token']}"
        }

        # * Send the request
        response = self.oauth.post(url_request, headers=headers_request, json=json_request)


        if response.status_code != 200:
            raise ValueError(f"Bad API response: {response.status_code}, {response.text}")

        content_type = response.headers.get("Content-Type", "")
        if "tiff" not in content_type.lower():
            raise ValueError(f"Unexpected content returned: {content_type}\n{response.text[:300]}")


        # * read the image as numpy array
        image_arr = np.array(Image.open(io.BytesIO(response.content)))

        return image_arr
    
    def save_band_as_tif(
        self,
        band_arr,
        band:str,
        bbox:list,
        start_date:str="",
        end_date:str="",
        output_path:str=""
        ):
        
        """saves the downloaded image as tiff files
        """
        
        import rasterio
        from rasterio.transform import from_bounds
        import numpy as np
        import os
        
        # * bbox = [minLon, minLat, maxLon, maxLat]
        transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], band_arr.shape[1], band_arr.shape[0])

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
            output_folder = f"./downloaded_images/sentinel2/{folder_name}"
            os.makedirs(output_folder, exist_ok=True)
            
            output_path = os.path.join(output_folder, file_name)
    
        # * Save with correct geo-referencing
        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=band_arr.shape[0],
            width=band_arr.shape[1],
            count=1,
            dtype=band_arr.dtype,
            crs='EPSG:4326',  # * SentinelHub returns WGS84
            transform=transform
        ) as dst:
            dst.write(band_arr, 1)
            
    def download_band(
        self,
        bbox:str,
        band:str,
        start_date:str,
        end_date:str
    ):
        bbox_to_fetch_image=bbox.split(',')
        image_arr=self.fetch_image(
                    bbox=bbox_to_fetch_image,
                    band=band,
                    start_date=start_date,
                    end_date=end_date,
                    )
        
        bbox_to_save_image = [float(x) for x in bbox.split(',')]
        self.save_band_as_tif(
            image_arr,
            band,
            bbox_to_save_image,
            start_date=start_date,
            end_date=end_date
        )
        
        
        
        
    