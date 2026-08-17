
# * other imports
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN
from skimage import measure
from shapely.geometry import Polygon
import geopandas as gpd
from rasterio.transform import Affine
import json
import cv2
import numpy as np
import matplotlib.pyplot as plt
from esda.moran import Moran
from libpysal.weights import lat2W
from scipy.ndimage import generic_filter
import requests
from collections import defaultdict
from skimage.filters import threshold_otsu
from typing import Union

# * r cropping
from rasterio.mask import mask
from shapely.geometry import box
from shapely.ops import transform
import pyproj
# from osgeo import osr

# import hdbscan
import os

# *for google API
from google import genai

import cv2 as cv
import numpy as np

# * segmentation labels without overlap

from skimage import data
from skimage.color import label2rgb
from skimage.filters import sobel
from skimage.measure import label
from skimage.segmentation import expand_labels, watershed

# * raster to vector
from shapely.geometry import shape
from rasterio import features


# * To covert to UTM
from pyproj import CRS
from pyproj.database import query_utm_crs_info
from rasterio.warp import calculate_default_transform, reproject, Resampling
import pylandstats as pls
from pyproj.aoi import AreaOfInterest

# * cation
import reverse_geocode

# * for image encoding
import io
import base64
from PIL import Image



class raster_engine:
    def __init__(self):
        
        self.dataset=dict()
        
        self.utm_projected_data=dict()  # * contains 'reprojected_data', 'transform', 'profile' for each 'src_name'=['red', 'green', blue', 'nir', 'swir']
        
        self.utm_projected_dataset = dict() # * contains only 'reprojected_data' for  each 'src_name'=['red', 'green', blue', 'nir', 'swir']
        
        self.water_thresholds={
                                'sentinel':0.2,
                                'landsat':0.2,
                                'liss_3':0.05,
                                'liss_4':0.08
                                }
        
        self.default_parent_dir_path_dict={
            "sentinel":"./downloaded_images/sentinel2",
            "landsat":"./downloaded_images/landsat9",
            "liss_3":"./downloaded_images/liss_3",
            "liss_4":"./downloaded_images/liss_4"
            }
        
        self.default_output_parent_dir_path_dict={
            "sentinel":"./IGARSS_raster_engine_outputs/sentinel2",
            "landsat":"./IGARSS_raster_engine_outputs/landsat9",
            "liss_3":"./IGARSS_raster_engine_outputs/liss_3",
            "liss_4":"./IGARSS_raster_engine_outputs/liss_4"
            }
        
        self.sensor_alias_names={
            "sentinel":["sentinel","sentinel2","sentinel_2"],
            "landsat":["landsat","landsat9","landsat_9"],
            "liss_3":["liss_3","liss3","lis3","lis_3"],
            "liss_4":["liss_4","liss4","lis4","lis_4"]
        }

#==============================================================================================================================================

    # > clear all data in the dataset and utm_projected_data dictionaries
    def clear_all_data(self):
        self.dataset=dict()
        self.utm_projected_data=dict()
        self.utm_projected_dataset = dict()

#==============================================================================================================================================

    #> open a raster file and store it in the dataset dictionary
    def open_raster(self,
                   raster_path:str=None,
                   name:str='-'):
        if name=='-':
            name='data_'+str(len(list(self.dataset.keys()))) # auto name if not provided as data_0, data_1, ...
        
        self.dataset[name]=rasterio.open(raster_path)
        
#==============================================================================================================================================

    # > get UTM EPSG code from bounds
    def get_utm_epsg_code_from_bounds(
        self,
        bounds,
        ):
        
        
        
        # * EGSP code simple formula
        west, south, east, north = bounds
        center_lon = (west + east) / 2
        
        # * Calculate UTM zone from center longitude
        utm_zone = int((center_lon + 180) / 6) + 1
        
        # * Determine if Northern (N) or Southern (S) hemisphere
        if south >= 0:
            hemisphere = 'N'
            utm_epsg = 32600 + utm_zone  # Northern: 32601-32660
        else:
            hemisphere = 'S'
            utm_epsg = 32700 + utm_zone  # Southern: 32701-32760
            
        #* EPSG code using pyproj
        aoi = AreaOfInterest(
                    west_lon_degree=west,
                    south_lat_degree=south,
                    east_lon_degree=east,
                    north_lat_degree=north
                    )
        
        utm_list = query_utm_crs_info(
                        datum_name="WGS 84",
                        area_of_interest=aoi
                        )
        
        if not utm_list:
            #* fall back to simple formula
            print(f'! simple UTM EPSG code used, code:{utm_epsg}')
            return str(utm_epsg)
        
        #* pick the first result
        print(f'! pyproj UTM EPSG code used, code:{utm_epsg}')
        crs_info = utm_list[0]
        return crs_info.code
        
#==============================================================================================================================================

    # > reproject raster to UTM
    def reproject_to_UTM(self,
                         src_name,
                         return_data=False):
        
        src=self.dataset[src_name]
        band_data=src.read(1)
        src_crs = src.crs
        src_transform = src.transform
        src_profile = src.profile.copy()
        
        
        bounds=src.bounds
        utm_epsg_code=self.get_utm_epsg_code_from_bounds(bounds)
        
        utm_crs = CRS.from_epsg(utm_epsg_code)
        # dst_crs=f"EPSG:{utm_epsg_code}"
        
        transform, width, height = calculate_default_transform(
            src_crs,
            # dst_crs,
            utm_crs,
            src.width, src.height,
            *src.bounds
        )
    
        # Create output array
        reprojected_data = np.zeros((height, width), dtype=band_data.dtype)
        
        # Perform reprojection
        reproject(
            band_data,
            reprojected_data,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=transform,
            # dst_crs=dst_crs,
            dst_crs=utm_crs,
            resampling=Resampling.bilinear
        )
        
        # * Update profile for new CRS
        profile = src_profile.copy()
        profile.update({
            # 'crs': dst_crs,
            'crs':utm_crs,
            'transform': transform,
            'width': width,
            'height': height
        })
        
        self.utm_projected_data[src_name]={
                                            'reprojected_data':reprojected_data,
                                            'transform':transform,
                                            'profile':profile
                                            }
        self.utm_projected_dataset[src_name]=reprojected_data
        if return_data:
            return reprojected_data, transform, profile

#==============================================================================================================================================

    #> function for opening sentinel bands
    def open_band_from_dir(self,
                           sensor:str,
                           dir_path,
                           clear_all_data=True):
        '''function for opening sentinel bands from a directory'''
        if clear_all_data:
            self.clear_all_data()
        
        sensor=sensor.lower()

        if sensor not in self.sensor_alias_names['sentinel'] + self.sensor_alias_names['landsat'] + self.sensor_alias_names['liss_3'] + self.sensor_alias_names['liss_4']:
            print('sensor not supported yet')
            return None
        
        band_img_suffix={}

        if sensor in self.sensor_alias_names['sentinel']:
            band_img_suffix={
                'blue':'B02.tif',
                'green':'B03.tif',
                'red':'B04.tif',
                'nir':'B08.tif',
                'swir':'B11.tif'
            }

        elif sensor in self.sensor_alias_names['landsat']:
            band_img_suffix={
                'blue':'B2.tif',
                'green':'B3.tif',
                'red':'B4.tif',
                'nir':'B5.tif',
                'swir':'B6.tif'
            }

        elif sensor in self.sensor_alias_names['liss_4']:
            band_img_suffix={
                'blue':False,
                'green':'2.tif',
                'red':'3.tif',
                'nir':'4.tif',
                'swir':False
            }
            
        elif sensor in self.sensor_alias_names['liss_3']:
            band_img_suffix={
                'blue':False,
                'green':'2.tif',
                'red':'3.tif',
                'nir':'4.tif',
                'swir':'5.tif'
            }

        band_imgs=os.listdir(dir_path)
        band_imgs_paths=[os.path.join(dir_path,band_img) for band_img in band_imgs if band_img.endswith('.tif')]    #* getting path of all contents in the directory
        
        bands_dict={}
        
        if not band_img_suffix['blue'] and 'blue' in list(self.dataset.keys()):  # * remove blue band because it might be present for other sensor
            self.dataset.pop('blue')

        for bands_imgs_path in band_imgs_paths:         #* using only tiff images and identifying band paths

            if band_img_suffix.get('blue') and bands_imgs_path.endswith(band_img_suffix.get('blue')):   #* checking if blue band is available
                bands_dict['blue_band_path']=bands_imgs_path

            elif bands_imgs_path.endswith(band_img_suffix.get('green')):
                bands_dict['green_band_path']=bands_imgs_path

            elif bands_imgs_path.endswith(band_img_suffix.get('red')):
                bands_dict['red_band_path']=bands_imgs_path
            
            elif bands_imgs_path.endswith(band_img_suffix.get('nir')):
                bands_dict['nir_band_path']=bands_imgs_path
                
            elif band_img_suffix.get('swir') and bands_imgs_path.endswith(band_img_suffix.get('swir')):
                bands_dict['swir_band_path']=bands_imgs_path
        
        for key,band_path in bands_dict.items():   #* checking if all required bands are found

            if key in ['blue_band_path','green_band_path','red_band_path','nir_band_path','swir_band_path']:
                #* opening bands
                self.open_raster(raster_path=band_path,
                                 name=key.split('_')[0])
            else:
                print(f'{key} not found')
                return None
            
        # self.open_raster(raster_path=bands_dict['red_band_path'], # opening bands
        #         name='red')
        # self.open_raster(raster_path=bands_dict['blue_band_path'],
        #             name='blue')
        # self.open_raster(raster_path=bands_dict['green_band_path'],
        #             name='green')
        # self.open_raster(raster_path=bands_dict['nir_band_path'],
        #         name='nir')

#==============================================================================================================================================

    #>extract a band from the raster file
    def extract_band(self,
                     raster_path=None,
                     src_name:str=None):
        if type(raster_path)!=type(None) and src_name==None:
            with rasterio.open(raster_path) as src:
                return src.read(1).astype('float32')
            
        elif type(raster_path)==type(None) and src_name!=None:
            return self.dataset[src_name].read(1).astype('float32')
        
#==============================================================================================================================================

    #> extract UTM projected band
    def extract_utm_band(self,
                         src_name:str):
        return self.utm_projected_dataset[src_name].astype('float32')
    
#==============================================================================================================================================

    # > checking if the coordinates are in geographic format
    def is_geo_coord(self,
                     lon_or_x, lat_or_y):
        """
        Determines if a coordinate is likely in Geographic (lat/lon)
        or Projected (e.g. UTM) coordinates.
        """
        # Geographic coordinates are usually between:
        # Longitude: -180 to 180, Latitude: -90 to 90
        if -180 <= lon_or_x <= 180 and -90 <= lat_or_y <= 90:
            return True
        
        # Projected coordinates (like UTM) are usually large numbers in meters
        elif abs(lon_or_x) > 1000 and abs(lat_or_y) > 1000:
            return False
        
        else:
            raise ValueError('Unidentified coordinates')

#==============================================================================================================================================

    # #> crop a raster file using a bounding box
    # def crop_raster(self,
    #                 bbox:Union[list,tuple],
    #                 raster_path:str=None,
    #                 src_name:str=None
    #                 ):
    #     """returns a cropped image from raster image

    #     Args:
    #         bbox (Union[list,tuple]): cropping area bounding box
    #         raster_path (str, optional): Path of the raster image. Defaults to None.
    #         src_name (str, optional): Name of the raster image in rp.dataset dictionary, if band was already opened. Defaults to None.

    #     Raises:
    #         ValueError: Either src_name or raster_path is required otherwise error will be raised

    #     Returns:
    #         type(rp.dataset['red']): cropped raster image
            
    #     Example:
    #         rp.crop_raster(bbox=box(292252,2357970,370352,2419745),
    #                        src_name='red')
    #     """
        
    #     bbox=box(*bbox)  # create a shapely box from the bbox coordinates

    #     if not isinstance(raster_path,type(None)) and src_name==None:
    #     # if type(raster_path)!=type(None) and src_name==None:
    #         with rasterio.open(raster_path) as src:
    #             cropped_img, cropped_transform = mask(src, [bbox], crop=True)
    #             cropped_img = cropped_img.astype('float32')
    #             cropped_meta = src.meta.copy()
    #             cropped_meta.update({
    #                 "height": cropped_img.shape[1],
    #                 "width": cropped_img.shape[2],
    #                 "transform": cropped_transform
    #                 })
                
    #     elif isinstance(raster_path,type(None)) and src_name!=None:
    #     # elif type(raster_path)==type(None) and src_name!=None:

    #         # getting the raster's CRS and defining transformers
    #         to_crs_str=self.dataset[src_name].crs.to_string()
    #         sr = osr.SpatialReference()
    #         sr.ImportFromWkt(to_crs_str)
    #         to_crs_name=sr.GetAttrValue("AUTHORITY", 1)

    #         # Define projection transformers
    #         default_crs=pyproj.CRS("EPSG:4326")   # WGS84 lat/lon
    #         to_crs = pyproj.CRS(f"EPSG:{to_crs_name}") # UTM zone from the raster
            
    #         project = pyproj.Transformer.from_crs(
    #                                               default_crs,
    #                                               to_crs,
    #                                               always_xy=True
    #                                               ).transform
            
    #         # Transform the bbox geometry
    #         bbox_utm = transform(project, bbox)

            

    #         cropped_img, cropped_transform = mask(self.dataset[src_name], [bbox_utm], crop=True)
    #         cropped_img = cropped_img.astype('float32')
    #         cropped_meta = self.dataset[src_name].meta.copy()
    #         cropped_meta.update({
    #             "height": cropped_img.shape[1],
    #             "width": cropped_img.shape[2],
    #             "transform": cropped_transform
    #             })
    #     else:
    #         raise ValueError("Please provide a path or src_name")
        
    #     return cropped_img[0], cropped_transform, cropped_meta
    
    # ! This function has bug
    # > reproject bbox to UTM
    # def reproject_bbox_to_utm(self,
    #                           bbox:Union[list,tuple,box],
    #                           raster:rasterio.io.DatasetReader):
    #     """Takes a list of geo coordinate in format [lon_min,lat_min,lon_max,lat_max]/box geometry with raster image(for extracting correct crs to project in). Returns a utm projected box geometry.

    #     Args:
    #         bbox (Union[list,tuple,shapely.geometry.polygon.Polygon]): list/tuple of coordinates/ box geometry
    #         raster (rasterio.io.DatasetReader): raster image (the coordinate must be covered by the bounds of the raster image)

    #     Returns:
    #         shapely.geometry.polygon.Polygon: utm projected box geometry
    #     """
        
    #     if type(bbox) in [list,tuple]:
    #         bbox=box(*bbox)
        
    #     # getting the raster's CRS and defining transformers
    #     to_crs_str=raster.crs.to_string()
    #     sr = osr.SpatialReference()
    #     sr.ImportFromWkt(to_crs_str)
        
    #     # ! This part returns nothing hence '''pyproj.CRS(f"EPSG:{to_crs_name}")''' will fail
    #     to_crs_name=sr.GetAttrValue("AUTHORITY", 1)

    #     # Define projection transformers
    #     default_crs=pyproj.CRS("EPSG:4326")   # WGS84 lat/lon
    #     to_crs = pyproj.CRS(f"EPSG:{to_crs_name}") # UTM zone from the raster
        
    #     project = pyproj.Transformer.from_crs(
    #                                             default_crs,
    #                                             to_crs,
    #                                             always_xy=True
    #                                             ).transform
        
    #     # Transform the bbox geometry
    #     bbox_utm = transform(project, bbox)
        
    #     return bbox_utm
        
    
    # ! function has bug from "reproject_bbox_to_utm" function
    #> crop a raster file using a bounding box
    # def crop_raster(self,
    #                 bbox:Union[list,tuple],
    #                 raster_path:str=None,
    #                 src_name:str=None
    #                 ):
    #     """returns a croped image from raster image

    #     Args:
    #         bbox (Union[list,tuple]): cropping area bounding box
    #         raster_path (str, optional): Path of the raster image. Defaults to None.
    #         src_name (str, optional): Name of the raster image in rp.dataset dictionary, if band was already opened. Defaults to None.

    #     Raises:
    #         ValueError: Either src_name or raster_path is required otherwise error will be raised

    #     Returns:
    #         type(rp.dataset['red']): cropped raster image
            
    #     Example:
    #         rp.crop_raster(bbox=box(292252,2357970,370352,2419745),
    #                        src_name='red')
    #     """
        
    #     raster_img=None
    #     #* open the raster if path was given
    #     if not isinstance(raster_path,type(None)) and src_name==None:
    #         raster_img= rasterio.open(raster_path)
            
    #     elif isinstance(raster_path,type(None)) and src_name!=None:
    #         raster_img=self.dataset[src_name]
            
        
            
    #     #* check for crs miss-match
    #     #* if raster is utm projected and bbox is in geo coord then reproject bbox to utm
    #     if raster_img.crs.is_projected:
    #         if self.is_geo_coord(lon_or_x=bbox[0],lat_or_y=bbox[1]):
    #             bbox=self.reproject_bbox_to_utm(bbox=bbox,
    #                                             raster=raster_img)
                
    #         #* if both are utm projected --> create a shapely box
    #         else: bbox=box(*bbox)
            
    #     #* if raster is in geo coord and bbox is in utm projected coord --> raise error
    #     elif not raster_img.crs.is_projected:
    #         if not self.is_geo_coord(lon_or_x=bbox[0],lat_or_y=bbox[1]):
    #             raise ValueError('Provided bbox is in projected coordinate system but raster is in geographic coordinate system')
            
    #         #* if both have gro crs --> create a shapely box
    #         else: bbox=box(*bbox)
                
        
    #     # * crop the raster
    #     cropped_img, cropped_transform = mask(raster_img, [bbox], crop=True)
    #     cropped_img = cropped_img.astype('float32') 
    #     cropped_meta = raster_img.meta.copy()
    #     cropped_meta.update({
    #         "height": cropped_img.shape[1],
    #         "width": cropped_img.shape[2],
    #         "transform": cropped_transform
    #         })
                
        
    #     return cropped_img[0], cropped_transform, cropped_meta
    
#==============================================================================================================================================

    #> plot a raster image
    def plot_raster(self,
                    raster:np.ndarray,
                    title:str="Raster Image",
                    cmap:str='gray',
                    figsize:tuple=(10,10),
                    axis_off_on='off',
                    show=True,
                    save_path:str=None
                    ):
        import numpy as np
        fig,axes=plt.subplots(figsize=figsize)
        # plt.figure(figsize=figsize)
        img=axes.imshow(raster, cmap=cmap)
        fig.colorbar(img, ax=axes, label='Pixel Values')
        axes.set_title(title)
        axes.axis(axis_off_on)
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight')

        if show: plt.show()

        return fig,axes

#==============================================================================================================================================

    #> print metadata of a raster file
    def print_metadata(self,
                       raster_path:str=None,
                       src_name:str=None):
        if type(raster_path)!=type(None) and src_name==None:
            with rasterio.open(raster_path) as tif:
                pass
        elif type(raster_path)==type(None) and src_name!=None:
            tif=self.dataset[src_name]
        else:
            raise ValueError("Please provide a path or src_name")
        
        print('Metadata: \n',tif.meta)

        print("\nCRS (Coordinate Reference System): ",tif.crs)

        print("Bounds: ", tif.bounds)

        print("Width, Height: ", tif.width, tif.height)

        print('transform: \n',tif.transform)
    
        print("Number of Bands: ", tif.count)

#==============================================================================================================================================

    # > NDVI
    def get_NDVI(self,
                 nir_band:np.ndarray,
                 red_band:np.ndarray
                 ):
        '''Normalized Difference Vegetation Index'''
        ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-10)  # Adding a small value to avoid division by zero
        return ndvi
    
#==============================================================================================================================================

    # > NDWI
    def get_NDWI(self,
                 nir_band:np.ndarray,
                 green_band:np.ndarray
                 ):
        '''Normalized Difference Water Index'''
        ndwi = (green_band - nir_band) / (green_band + nir_band + 1e-10)  # Adding a small value to avoid division by zero
        return ndwi
    
#==============================================================================================================================================
    
    # > MNDWI
    def get_MNDWI(self,
                  green_band:np.ndarray,
                  swir_band:np.ndarray
                  ):
        '''Modified Normalized Difference Water Index'''
        mndwi = (green_band - swir_band) / (green_band + swir_band )  # Adding a small value to avoid division by zero
        return mndwi
    
#==============================================================================================================================================

    # > SAVI
    def get_SAVI(self,
                 nir_band:np.ndarray,
                 red_band:np.ndarray,
                 L:float=0.5
                 ):
        '''Soil Adjusted Vegetation Index'''
        savi = ((nir_band - red_band) / (nir_band + red_band + L)) * (1 + L)
        return savi
    
#==============================================================================================================================================

    # > NDBI
    def get_NDBI(self,
                 swir_band:np.ndarray,
                 nir_band:np.ndarray
                 ):
        '''Normalized Difference Built-up Index'''
        ndbi = (swir_band - nir_band) / (swir_band + nir_band + 1e-10)  # Adding a small value to avoid division by zero
        return ndbi
    
#==============================================================================================================================================

    # > make composite image
    def create_composite(self,
                         pick_auto:bool=False,
                         sensor:str='',
                         bands:dict={},
                         order:list=[],
                         normalize:bool=True
                         ):
        '''Create a composite image from individual bands.
        bands: A dictionary where keys are band names and values are 2D numpy arrays.
        order: A list specifying the order of bands in the composite image.
        normalize: If True, normalize each band to the range [0, 1].
        '''        
        
        # * make order automatically based on sensor
        if pick_auto:
            sensor=sensor.lower()
            if sensor in self.sensor_alias_names['sentinel']:
                order=['red','green','blue']
            elif sensor in self.sensor_alias_names['landsat']:
                order=['red','green','blue']
            elif sensor in self.sensor_alias_names['liss_3']:
                order=['swir','nir','red']
            elif sensor in self.sensor_alias_names['liss_4']:
                order=['nir','red','green']
            else:
                print('sensor not supported for auto band selection')
                return None
            
            # * check if bands are already present
            needed_bands=set(order)
            available_bands=set(self.dataset.keys())
            if not needed_bands.issubset(available_bands):
                unavailable_bands=needed_bands - available_bands
                print(f'{unavailable_bands} bands not present in dataset')
                return None
            
            else:
                bands={band_name:self.extract_band(src_name=band_name) for band_name in order}
        
        
        composite = []
    
        for band_name in order:
            
            band = bands[band_name].astype(np.float32)
            
            if normalize:
                
                
                band[~np.isfinite(band)] = np.nan
                
                band_min = np.nanmin(band)
                band_max = np.nanmax(band)
                
                # print(band_min, band_max)
                
                if band_max > band_min:  # avoid divide-by-zero
                    band = (band - band_min) / (band_max - band_min)
                else:
                    band = np.zeros_like(band)
                    
            composite.append(band)
            
        composite_image = np.stack(composite, axis=-1)
        return composite_image
    
#==============================================================================================================================================

    # > make otsu mask
    def otsu_mask(self,
                  index:np.ndarray,
                  threshold:float=None
                  ):
        '''Generate binary mask using Otsu's threshold method
        eg: ndvi_otsu,ndvi_otsu_threshold=rp.otsu_mask(index=ndvi_whole)
        '''
        # if threshold is None:
        #     threshold, _ = cv2.threshold((index * 255).astype(np.uint8),
        #                                  0,
        #                                  255,
        #                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        #     threshold = threshold / 255.0  # Normalize back to [0, 1]
        # binary_mask = (index >= threshold).astype(np.uint8)
        # return binary_mask, threshold
        if threshold is None:
            valid_index = index[~np.isnan(index)]  # ignore NaNs
            # min_val=min(valid_index)
            # max_val=max(valid_index)
            # threshold=0.2+(min_val+max_val)/2
            threshold = threshold_otsu(valid_index)
        mask = index > threshold  # vegetation mask
        return mask, threshold
    
#==============================================================================================================================================

    # > make binary mask with custom threshold
    def custom_mask(self,
                    index:np.ndarray,
                    heuristic:str='',
                    threshold:float=None
                    ):
        """Make binary mask based on your own threshold or calculate threshold using mean/median.

        Returns:
            tuple: (binary mask, threshold)
        """
        if heuristic=='mean' or heuristic=='median':
            if heuristic=='mean':
                water_mask=index>0.2
                threshold=np.mean(index[water_mask])

            elif heuristic=='median':
                water_mask=index>0.2
                threshold=np.median(index[water_mask])
                
        elif threshold==None and heuristic=='':
            raise ValueError('please provide a heuristic or a threshold')
            
        mask = index > threshold

        return mask,threshold
    
#==============================================================================================================================================

    # > make water mask
    def make_water_mask(
                    self,
                    sensor:str,
                    ndwi:np.ndarray,):
        threshold=self.water_thresholds[sensor]
        
        mask = ndwi > threshold
        return mask

#==============================================================================================================================================
    # ! omni water mask
    def make_omniwatermask(
        self,
        stacked_image_path:list
    ):
        
        # Predict water masks for scenes
        water_mask_path = make_water_mask(
            scene_paths=stacked_image_path,  # you can pass a list of images
            band_order=[1,2,3,4],  # band order of the input images, expects RGB+NIR
        )
        
        water_mask = rio.open(water_mask_path[0]).read(
            1,
            )
        return water_mask

#==============================================================================================================================================

    #> Function to compute Global Moran's I
    def compute_global_moran(self,
                             ndvi_sub):
        """Calculates morans' I for a mask (mask can be NDVI, NDBI or other)

        Args:
            ndvi_sub (numpy.array): mask

        Returns:
            tuple: _description_
        """
        
        # mask invalid values
        valid_mask = np.isfinite(ndvi_sub)
        invalid_mask = ~np.isfinite(ndvi_sub)

        if valid_mask.sum() < 10:
            return np.nan, np.nan

        values = ndvi_sub[valid_mask]

        if np.var(values) == 0:
            return np.nan, 1.0
        
        
        # * fill invalid values with minimum value
        ndvi_sub[invalid_mask]=np.min(ndvi_sub[valid_mask])
          
        w = lat2W(ndvi_sub.shape[0], ndvi_sub.shape[1])
        w.transform = "r"
        ndvi_flat = ndvi_sub.flatten()
        moran = Moran(ndvi_flat, w, permutations=999)
        return moran.I, moran.p_sim

#==============================================================================================================================================

    # > calculate class metrics for vegetation and built-up
    def cal_class_metrics(
        self,
        classified_vals,
        classes:list,
        nodata_val=0,
        transform=None
        ):
        """\
        !!!Warning!!!:
            transform should be UTM projected
            
        Summary:
            Function to get summary of patches in a class. It takes a mask, for example vegetation mask with classes "healthy", "moderate" and "bare_land".
        
        Workflow:
            checks if UTM projected data is already present (stored in self.utm_projected_data). If not then needs argument for transform parameter. Calculates resolution; needed for using PyLandStats. Then uses PyLandStats to calculate class metrics.
            
        Args:
            classified_vals (numpy.array): a mask of classified values 
            classes (list): class values from mask for which metrics needs to be calculated
            nodata_val (int, optional): value representing no data in mask. Defaults to 0.
            transform (affine.Affine, optional): Transform of UTM projected band. Defaults to None.

        Returns:
            pandas.Dataframe: dataframe of calculated class metrics. Metrics =['total_area',
                                                                               'proportion_of_landscape',
                                                                               'number_of_patches',
                                                                               'patch_density',
                                                                               'largest_patch_index',
                                                                               'total_edge',
                                                                               'edge_density',
                                                                               'landscape_shape_index',
                                                                               'euclidean_nearest_neighbor_mn']
        """
        
        if transform==None and len(self.utm_projected_data)==0:
            print('UTM projected data not present, provide transform of UTM projected')
            return
        
        elif transform==None and len(self.utm_projected_data):
            transform=list(self.utm_projected_data.values())[0]['transform']
            
        resolution=(abs(transform[0]), abs(transform[4]))
        
        
        # landscape = pls.Landscape(
        # classified_vals,
        # res=res,
        # nodata=0  # No data value
        # )
        
        landscape = pls.Landscape(
        classified_vals,
        res=resolution,
        nodata=nodata_val  # No data value
        )
        
        class_metrics= landscape.compute_class_metrics_df(
                                            classes=classes,  # All vegetation classes
                                            metrics=[
                                                'total_area',              # Total area per class (hectares)
                                                'proportion_of_landscape', # % of landscape
                                                'number_of_patches',       # Count of patches
                                                'patch_density',           # Patches per 100 hectares
                                                'largest_patch_index',     # % in largest patch (0-100)
                                                'total_edge',              # Total edge length (meters)
                                                'edge_density',            # Edge length per hectare
                                                'landscape_shape_index',   # Shape complexity (1=compact, >1=complex)
                                                'euclidean_nearest_neighbor_mn'  # Avg distance to nearest same-class patch
                                                ]
                                            )
        return class_metrics
    
#==============================================================================================================================================

    # > compute kernel size for morphological operations
    def adaptive_merge_distance(self,
                                pixel_size,
                                merge_distance_m=100
                                ):
        """
        pixel_size: ground resolution (m/pixel)
        merge_distance_m: how close water bodies can be merged (in meters)
        returns: kernel size in pixels (odd integer)
        """
        radius_px = int(np.ceil(merge_distance_m / pixel_size))
        kernel_size = 2 * radius_px + 1
        
        # if dist_px % 2 == 0: # make it odd for having a center pixel
        #     dist_px += 1
        return max(3, kernel_size) 
    
#==============================================================================================================================================

    # > remove small water bodies and expand and join big water bodies
    def refine_water_mask(self,
                          mask,
                          pixel_area_m2,
                          min_area_m2=5000,
                          merge_distance=5):
        """
        mask: binary NDWI mask (uint8, 0 or 255)
        pixel_area_m2: area covered by one pixel in m2
        min_area_m2: minimum area to keep in m2. If area of the body is smaller, then it will be removed
        merge_distance: how close separate blobs can be to be merged (in pixels)
        """
        # Step 1: Morphological closing to merge close patches
        kernel = cv.getStructuringElement(
            cv.MORPH_ELLIPSE,
            (merge_distance, merge_distance)
            )
        closed_mask = cv.morphologyEx(mask, cv.MORPH_CLOSE, kernel)
        
        # return closed_mask
        # Step 2: Remove very small blobs using connected components
        min_size_px = int(np.ceil(min_area_m2 / pixel_area_m2))
        
        num_labels, labels, stats, _ = cv.connectedComponentsWithStats(
            closed_mask, 
            connectivity=8
            )
        filtered = np.zeros_like(mask)
        for i in range(1, num_labels):
            area = stats[i, cv.CC_STAT_AREA]
            
            # if area >= min_size:
            if area >= min_size_px:
                filtered[labels == i] = 255
        
        return filtered

#==============================================================================================================================================

    # > divide mask in 4 cells
    def divide_in_quads(self,
                        mask):
        h, w = mask.shape
        h2, w2 = h // 2, w // 2
        q1 = mask[0:h2, 0:w2]
        q2 = mask[0:h2, w2:]
        q3 = mask[h2:, 0:w2]
        q4 = mask[h2:, w2:]
        
        return q1,q2,q3,q4

#==============================================================================================================================================

    # > get water body info
    def get_water_bodies_info(self,
                              water_mask,
                              transform:Affine=None,
                              crs=None,):
        '''Extract water bodies information from a binary water mask.
        water_mask: 2D numpy array (binary mask where water pixels are 1)
        transform: Affine transformation of the raster
        crs: Coordinate Reference System of the raster
        Returns: A dictionary with all water valid bodies info, top 10 largest water bodies, and main water bodies(area > 1% of largest).'''
        # make contours of the water mask
        contours = measure.find_contours(water_mask.astype(float), 0.5)
        

        # Function to convert pixel coordinates to geographic coordinates
        pixel_to_geo = lambda row, col, transform: rasterio.transform.xy(transform, row, col)

        # List to store water body information
        water_bodies_info=[]

        for contour in contours:
            # Close the contour if it is not already closed
            if not (np.allclose(contour[0], contour[-1])):
                contour = np.vstack([contour, contour[0]])

            # Convert pixel coordinates to geographic coordinates
            geo_coords = [pixel_to_geo(y, x, transform) for y, x in contour]  # Note: row = y, col = x
            
            # Create a polygon from the geographic coordinates
            poly = Polygon(geo_coords)

            # Check if the polygon is valid and has a significant area
            if poly.is_valid and poly.area > 1e-6:  # Filter small/invalid ones

                centroid = poly.centroid  # Get the centroid of the polygon
                area = poly.area  # Get the area of the polygon
                water_bodies_info.append({
                    "polygon": poly, # xxxx
                    "centroid": (centroid.x, centroid.y),  # Store centroid coordinates
                    "area_sqm": area,  # Store area in square meters
                    "boundary":geo_coords
                })
        # Sort water bodies by area
        water_bodies_info = sorted(water_bodies_info, key=lambda x: x['area_sqm'], reverse=True)
        
# =======

        # --- Step 3: Remove smaller overlapping polygons
        final_polygons = []
        kept_polys = []

        for wb in water_bodies_info:
            poly = wb['polygon']
            if not any(poly.intersects(kp) for kp in kept_polys):
                final_polygons.append(wb)
                kept_polys.append(poly)
            else:
                # Optional: keep it only if it is significantly distinct (e.g., overlap < 20%)
                overlaps = [poly.intersection(kp).area / poly.area for kp in kept_polys if poly.intersects(kp)]
                if all(overlap < 0.2 for overlap in overlaps):
                    final_polygons.append(wb)
                    kept_polys.append(poly)

        # sorting
        final_polygons=sorted(final_polygons, key=lambda x: x['area_sqm'], reverse=True)

        # --- Step 4: Top 10 and main bodies
        top_10_water_bodies = final_polygons[:10]
        largest_water_body = top_10_water_bodies[0] if top_10_water_bodies else None

        main_water_body_boundaries = []
        if largest_water_body:
            main_water_body_boundaries = [
                wb for wb in final_polygons
                if wb["area_sqm"] > largest_water_body['area_sqm'] * 0.01
            ]

        # --- Step 5: Remove Polygon objects before returning
        for wb in final_polygons:
            wb.pop("polygon", None)

        return {
            'all_water_bodies': final_polygons,
            'top_10_water_bodies': top_10_water_bodies,
            'main_water_bodies': main_water_body_boundaries
            
        }

#==============================================================================================================================================

    # > segmentation without overlap using Sobel and Watershed
    def segmentation_without_overlap(self,
                                 image:np.ndarray,
                                 expanding_distance=2,
                                 plot=False
                                 ):
        '''Segmentation without overlap using Sobel and Watershed'''

        # Make segmentation using edge-detection and watershed.
        edges = sobel(image)

        # Identify some background and foreground pixels from the intensity values.
        # These pixels are used as seeds for watershed.
        markers = np.zeros_like(image)
        foreground, background = 1, 2
        markers[image == 0] = background
        markers[image > 0] = foreground

        # Apply watershed algorithm
        ws = watershed(edges,
                       markers)

        # Label the segmented regions
        seg1 = label(ws == foreground)

        # Expand the labels to fill in gaps
        expanded = expand_labels(seg1,
                                 distance=expanding_distance)

        if plot:
            # Display results
            fig, axes = plt.subplots(
            nrows=1,
            ncols=3,
            figsize=(9, 5),
            sharex=True,
            sharey=True,
            )

            axes[0].imshow(image, cmap="Greys_r")
            axes[0].set_title("Original")

            color1 = label2rgb(seg1, image=image, bg_label=0)
            axes[1].imshow(color1)
            axes[1].set_title("Sobel+Watershed")

            color2 = label2rgb(expanded, image=image, bg_label=0)
            axes[2].imshow(color2)
            axes[2].set_title("Expanded labels")

            for a in axes:
                a.axis("off")
            fig.tight_layout()
            plt.show()

        return seg1, expanded
    
#==============================================================================================================================================

    # > extract polygons from segments
    def extract_polys_from_segs(self,
                                expanded_segments:np.ndarray,
                                transform
                                ):
        '''
        Description:
        - Takes expanded segments and returns a dictionary.
        - Keys in dictionary represent segment number (starts from 0)
        - Values in dictionary is a list of two GeoDataFrames which are [polygon_geometry_gdf, polygon_bounding_box_gdf]
        
        input: 
        Segments: np.ndarray

        output: A dictionary with :
            
            key: value names or polygon number (note value '0' represents background polygon, hence foreground polygons start from '1')
            
            value: List of GeoDataFrames: [polygons_gdf, polygons_bbox_gdf]
        '''
        # * imports
        from shapely.geometry import shape
        from rasterio import features
        
        total_values=expanded_segments.max()+1
        # print(total_values)
        poly_dict={}

        for v in range(total_values):
            mask = expanded_segments==v
            shapes = features.shapes(
                                     expanded_segments,
                                     mask=mask,
                                     transform=transform
                                     )
            # Convert all geometries to shapely polygons
            polygons = [shape(geom) for geom, value in shapes if value == v]
            poly_gdf = gpd.GeoDataFrame({'geometry':[polygons[i] for i in range(len(polygons))]})
            box_gdf = gpd.GeoDataFrame({'geometry':[box(*polygons[i].bounds) for i in range(len(polygons))]})
            poly_dict[str(v)] = [poly_gdf,box_gdf]

        return poly_dict
    
#==============================================================================================================================================

    # > code (numbers) for vegetation classes
    def get_vegetation_class_codes(
        self
        ):
        codes={
            1:"no vegetation",
            2:"bare ground or sparse vegetation",
            3:"moderate vegetation",
            4:"dense vegetation"
        }
        return codes


#============================================================================================================================================

    # > classify vegetation based on NDVI thresholds
    def classify_vegetation(
        self,
        ndvi):
        """Classifies NDVI into classes based on threshold.
        (ndvi > 0) & (ndvi < 0.2) = 1 bare/space
        (ndvi > 0.2) & (ndvi < 0.6) = 2 moderate
        (ndvi > 0.6) & (ndvi <= 1) = 3 dense/healthy

        Args:
            ndvi (numpy.array): NDVI

        Returns:
            numpy.array: mask with classified vegetation 
        """
        vegetation_codes=self.get_vegetation_class_codes()
        classes = np.zeros_like(ndvi)
        classes[ndvi<0] = next(k for k, v in vegetation_codes.items() if v=="no vegetation")  # complete lack of vegetation
        classes[(ndvi>=0) & (ndvi < 0.2)] = next(k for k, v in vegetation_codes.items() if v=="bare ground or sparse vegetation")  # bare/sparse
        classes[(ndvi >= 0.2) & (ndvi < 0.6)] = next(k for k, v in vegetation_codes.items() if v=="moderate vegetation")  # moderate
        classes[(ndvi >= 0.6) & (ndvi <= 1)] = next(k for k, v in vegetation_codes.items() if v=="dense vegetation")  # dense/healthy
        
        return classes

    
#==============================================================================================================================================

    # > code (numbers) for built-up classes
    def get_builtup_class_codes(
        self
        ):
        codes={
            1:"non built-up",
            2:"Medium-density built-up/stabilized desert",
            3:"High-density built-up areas"
        }
        return codes
    
#============================================================================================================================================

    # > classify built-up areas based on NDBI thresholds
    def classify_builtup(
        self,
        ndbi,
        sensor):
        """Classifies NDVI into classes based on threshold.
        (ndbi > 0) & (ndbi < 0.2) = 1 non built-up
        (ndbi > 0.2) & (ndbi < 0.3) = 2 Medium-density built-up/stabilized desert
        (ndbi > 0.3) & (ndbi < 1) = 3 High-density built-up areas

        Args:
            ndbi (numpy.array): NDBI

        Returns:
            numpy.array: mask with built-up 
        """
        built_up_class_thresholds=None
        if sensor in self.sensor_alias_names['liss_4']:
            built_up_class_thresholds={
                'non built-up':[-1, -0.6],
                "Medium-density built-up/stabilized desert":[-0.6, -0.2],
                "High-density built-up areas":[-0.2, 1]   # ! setting upper threhsold to 1.1 so that pixels with NDBI = 1 are not excluded
            }
            # built_up_class_thresholds={
            #     'non built-up':[-1, 0.2],
            #     "Medium-density built-up/stabilized desert":[0.2, 0.6],
            #     "High-density built-up areas":[0.6, 1]
            # }
        elif sensor in self.sensor_alias_names['landsat']:
            built_up_class_thresholds={
                'non built-up':[-1, 0.0],
                "Medium-density built-up/stabilized desert":[0.0, 0.2],
                "High-density built-up areas":[0.2, 1.1] # ! setting upper threhsold to 1.1 so that pixels with NDBI = 1 are not excluded
            }
        
        elif sensor in self.sensor_alias_names['sentinel']:
            built_up_class_thresholds={
                'non built-up':[-1, 0.05],
                "Medium-density built-up/stabilized desert":[0.05, 0.2],
                "High-density built-up areas":[0.2, 1.1]
            }
            
        elif sensor in self.sensor_alias_names['liss_3']:
            built_up_class_thresholds={
                'non built-up':[-1, -0.05],
                "Medium-density built-up/stabilized desert":[-0.05, 0.04],
                "High-density built-up areas":[0.04, 1.1]
            }
        builtup_class_codes=self.get_builtup_class_codes()
        
        classes = np.zeros_like(ndbi)
        
        # # classes[(ndbi>=0) & (ndbi < 0.2)] = 1  # no built-up
        # classes[ndbi < 0.2] = next(k for k, v in builtup_class_codes.items() if 'non' in v)  # no built-up
        # classes[(ndbi >= 0.2) & (ndbi < 0.6)] = next(k for k, v in builtup_class_codes.items() if 'Medium' in v)  # moderate
        # classes[(ndbi >= 0.6) & (ndbi <= 1)] = next(k for k, v in builtup_class_codes.items() if 'High' in v)  # dense/healthy
        
        for class_name,class_th in built_up_class_thresholds.items():
            
            lower_th, upper_th = class_th
            
            
            classes[(ndbi >= lower_th) & (ndbi < upper_th)] = next(num_code for num_code, cn in builtup_class_codes.items() if cn==class_name)
            
        
        return classes
    
#==============================================================================================================================================

    # > classify built-up areas based on NDBI thresholds for lis3 sensor
    def classify_lis3_builtup(
        self,
        ndbi):
        """Classifies NDVI into classes based on threshold for lis3 sensor.
        (ndbi > 0) & (ndbi < 0.2) = 1 non built-up
        (ndbi > 0.2) & (ndbi < 0.3) = 2 Medium-density built-up/stabilized desert
        (ndbi > 0.3) & (ndbi < 1) = 3 High-density built-up areas

        Args:
            ndbi (numpy.array): NDBI

        Returns:
            numpy.array: mask with built-up 
        """
        builtup_class_codes=self.get_builtup_class_codes()
        classes = np.zeros_like(ndbi)
        # classes[(ndbi>=-0.1) & (ndbi < -0.05)] = 1  # no built-up
        classes[ndbi < -0.05] = next(k for k, v in builtup_class_codes.items() if 'non' in v)  # no built-up
        classes[(ndbi >= -0.05) & (ndbi < 0.04)] = next(k for k, v in builtup_class_codes.items() if 'Medium' in v)  # moderate
        classes[(ndbi >= 0.04) & (ndbi <= 1)] = next(k for k, v in builtup_class_codes.items() if 'High' in v)  # dense/healthy
        
        return classes
    
#============================================================================================================================================

    # > calculate vegetation coverage percentage based on NDVI thresholds
    def vegetation_coverage(
        self,
        ndvi,
        lower_threshold,
        upper_threshold):
        
        total_pixels = ndvi.size
        vegetated_pixels = np.sum((ndvi >= lower_threshold) & (ndvi<upper_threshold))
        coverage = (vegetated_pixels / total_pixels) * 100
        # print(f"Vegetation covers {coverage:.2f}% of the area.")
        return coverage
    
#============================================================================================================================================

    # > calculate vegetation class coverage percentage
    def vegetation_class_coverage_percent(
        self,
        classified_veg
        ):
        
        vegetation_codes=self.get_vegetation_class_codes()
        
        total_pixels = classified_veg.size
        coverage=dict()
        
        for c in range(1,int(classified_veg.max())+1):
            
            vegetated_pixels = np.sum(classified_veg==c)
            coverage[vegetation_codes[c]] = (vegetated_pixels / total_pixels) * 100
            
        coverage_info={
            'coverage_info':coverage,
            'unit':'%'
            }
        
        return coverage_info
    
#============================================================================================================================================
    # > gives vegetation class coverage area
    def vegetation_class_coverage_area(
        self,
        classified_veg,
        any_src_name:str=None,
        pixel_area_km2:Union[float, int]=None,
        pixel_area_m2:Union[float, int]=None
        ):
        """Takes classified vegetation mask i.e. mask with values [1,2,3] representing [bare land, moderate vegetation, dense vegetation] respectively and arguments for one of [any_src_name, pixel_area_k2, pixel_area_m2], for calculating pixel area. Returns coverage area for each class in either km2 or m2.
        
        Note: Unit of area will be taken as "m2" only when value for pixel_area_m2 is passed and no value are passed for any_src_name and pixel_area_km2, i.e. any_src_name = None and pixel_area_km2 = None.

        Args:
            classified_veg (np.ndarray): classified vegetation mask
            any_src_name (str, optional): name of any of the band that was user for generating "classified vegetation mask". for example "red" or "nir" when mask is ndvi. Defaults to None.
            pixel_area_km2 (float, int, optional): area covered by each pixel in km2. Defaults to None.
            pixel_area_m2 (float, int, optional): area covered by each pixel in m2. Defaults to None.

        Raises:
            ValueError: _description_

        Returns:
            _type_: _description_
        """
        
        if any_src_name==None and pixel_area_km2==None and pixel_area_m2==None:
            raise ValueError("pass argument for one of the parameters [any_src_name, pixel_area_km2, pixel_area_m2]")
        
        area_per_pixel=None
        if any_src_name!=None:
            pixel_info=self.get_area_per_pixel(src_name=any_src_name)
            area_per_pixel={
                'area':pixel_info['pixel_area_km2'],
                'unit':'km2'}
            
        elif pixel_area_km2!=None:
            area_per_pixel={
                'area':pixel_area_km2,
                'unit':'km2'}
        
        else:
            area_per_pixel={
                'area':pixel_area_m2,
                'unit':'m2'}
        
        # *get codes for vegetation types
        vegetation_codes=self.get_vegetation_class_codes()
        
        # total_pixels = classified_veg.size
        # total_area = area_per_pixel['area']*classified_veg.size
        
        coverage=dict()
        
        for c in range(1,int(classified_veg.max())+1):
            
            vegetation_pixels = np.sum(classified_veg==c)
            coverage[vegetation_codes[c]] = vegetation_pixels*area_per_pixel['area']
            
        return {'coverage_info':coverage, 'unit':area_per_pixel['unit']}

    
#============================================================================================================================================

    # > calculate built-up class coverage percentage 
    def built_up_class_coverage_percent(
        self,
        classified_builtup):
        
        total_pixels = classified_builtup.size
        coverage=dict()
        
        builtup_class_codes=self.get_builtup_class_codes()
        
        for c in range(1,int(classified_builtup.max())+1):
            
            vegetated_pixels = np.sum(classified_builtup==c)
            coverage[builtup_class_codes[c]] = (vegetated_pixels / total_pixels) * 100
            
        coverage_info={
            'coverage':coverage,
            'unit':'%'
            }
        return coverage_info
    
#============================================================================================================================================

    # > gives built-up class coverage area
    def built_up_class_coverage_area(
        self,
        classified_builtup,
        any_src_name:str=None,
        pixel_area_km2:Union[float, int]=None,
        pixel_area_m2:Union[float, int]=None
        ):
        """Takes classified built-up mask i.e. mask with values [1,2,3] representing [no built-up, moderate built-up, dense built-up] respectively and arguments for one of [any_src_name, pixel_area_k2, pixel_area_m2], for calculating pixel area. Returns coverage area for each class in either km2 or m2.
        
        Note: Unit of area will be taken as "m2" only when value for pixel_area_m2 is passed and no value are passed for any_src_name and pixel_area_km2, i.e. any_src_name = None and pixel_area_km2 = None.

        Args:
            classified_builtup (np.ndarray): classified built-up mask
            any_src_name (str, optional): name of any of the band that was user for generating "classified built-up mask". for example "nir" or "swir". Defaults to None.
            pixel_area_km2 (float, int, optional): area covered by each pixel in km2. Defaults to None.
            pixel_area_m2 (float, int, optional): area covered by each pixel in m2. Defaults to None.

        Raises:
            ValueError: _description_

        Returns:
            _type_: _description_
        """
        
        if any_src_name==None and pixel_area_km2==None and pixel_area_m2==None:
            raise ValueError("pass argument for one of these parameters [any_src_name, pixel_area_km2, pixel_area_m2]")
        
        area_per_pixel=None
        
        if any_src_name!=None:
            pixel_info=self.get_area_per_pixel(src_name=any_src_name)
            area_per_pixel={
                'area':pixel_info['pixel_area_km2'],
                'unit':'km2'}
            
        elif pixel_area_km2!=None:
            area_per_pixel={
                'area':pixel_area_km2,
                'unit':'km2'}
        
        else:
            area_per_pixel={
                'area':pixel_area_m2,
                'unit':'m2'}
        
        # *get codes for built-up types
        builtup_codes=self.get_builtup_class_codes()
        
        coverage=dict()
        
        for c in range(1,int(classified_builtup.max())+1):
            
            builtup_pixels = np.sum(classified_builtup==c)
            coverage[builtup_codes[c]] = builtup_pixels*area_per_pixel['area']
            
        return {'coverage_info':coverage, 'unit':area_per_pixel['unit']}
    
    
#==============================================================================================================================================

    # > make valid path for python
    def make_valid_path(
        self,
        path:str
        )->str:
        """coverts windows path with "\\" to "/"
        
        !Warning: use "r" before the path string to avoid escape character issues.
        e.g: r"C:\\xvz\\abc..

        Args:
            path (str): windows format path (pass this way: r"C:\\xvz\\abc..")

        Returns:
            str: valid path for python with all "/" replaced with "/"
        """
        return path.replace('\\','/')
    
#==============================================================================================================================================

    # > dump as json
    def save_in_json(
        self,
        content:dict,
        path:str,
        file_name:str
        ):
        """Saves a dictionary as json file.

        Args:
            content (dict): Dictionary containing the content
            path (str): The directory in which json file will be saved, for eg. "C/abc/.../sentinel/all_bands"
            file_name (str): Name of the json file, for eg. "water_info.json"
        """
        correct_file_name=file_name.split(".json")[0]+".json"
        with open(os.path.join(path,correct_file_name), "w") as f:
            json.dump(content, f)
       
#==============================================================================================================================================
    # > get area per pixel and total area covered by raster
    def get_area_per_pixel(
        self,
        src_name
    ):
        """Takes the src_name ("red", "blue", ..), takes the already opened raster and gives the total area covers by the raster. If raster is in geo coordinates system then it first projects it into UTM then calculates the area.

        Args:
            src_name (string): name of one of the open bands ("red", "blue", "green", "nir", "swir").

        Returns:
            dict(): dictionary containing info about [default crs of the raster, total area covered in meter square, total area in km square, area/pixel in meter square, area/pixel in km square]
        """
        
        src=self.dataset[src_name]
        
        crs = CRS.from_wkt(src.crs.to_wkt())
        transform = src.transform
        width = src.width
        height = src.height
        bounds = src.bounds
        
        if crs.is_projected and crs.axis_info[0].unit_name == "metre":
            pixel_area_m2 = abs(transform.a * transform.e)
            total_area_m2 = pixel_area_m2 * width * height
            
        else:
            epsg_code=self.get_utm_epsg_code_from_bounds(
                bounds=src.bounds
            )
            utm_crs = CRS.from_epsg(epsg_code)
            
            # Reproject raster to UTM in-memory
            transform_utm, width_utm, height_utm = calculate_default_transform(
                src.crs, utm_crs, width, height, *bounds
            )

            pixel_area_m2 = abs(transform_utm.a * transform_utm.e)
            total_area_m2 = pixel_area_m2 * width_utm * height_utm

        return {
            "crs_type": "projected" if crs.is_projected else "geographic",
            "total_area_m2": total_area_m2,
            "total_area_km2": total_area_m2 / 1e6,
            "pixel_area_m2": pixel_area_m2,
            "pixel_area_km2": pixel_area_m2 / 1e6
    }
            
#==============================================================================================================================================
    
    # > divide map in grid cells
    def make_cells(
        self,
        mask: np.ndarray,
        nrows: int,
        ncols: int) -> list:
        h, w = mask.shape

        row_heights = np.linspace(0, h, nrows + 1, dtype=int)
        col_widths  = np.linspace(0, w, ncols + 1, dtype=int)

        cell_list = []

        for i in range(nrows):
            for j in range(ncols):
                cell = mask[
                    row_heights[i]:row_heights[i + 1],
                    col_widths[j]:col_widths[j + 1]
                ]
                cell_list.append(cell)

        return cell_list


#============================================================================================================================================
    
    # > plot multiple images/masks on one area
    def plot_all_on_one(self,
        figsize:tuple=(16,16),
        nrows:int=2,
        ncols:int=2,
        titles:list=[],
        images:list=[],
        cmaps:list=[],
        legends:list=[],
                        
        # * params for color bar
        show_colorbar:list=[],
        fraction=0.046,
        pad=0.04
        ):
        """!!!Warning!!!
        length of "images", "titles", "cmaps" and "show_colorbar" must be equal.
        
        Summary:
        plots all images/masks on one area.
        
        Note:
            * title skip value: if don't want to pass title for a image, then pass "". 
                                Example:
                                    images=[ndvi,q1,q2,q3,q4]
                                    titles=["ndvi full image",
                                            "1st quad"
                                            "",                # title will be skipped for 2nd image
                                            "3rd quad",
                                            "4th quad"]
                                            
            * cmap skip value: if don't want to pass cmap value for a image, then pass None.
                               Example:
                                    images=[ndvi,q1,q2,q3,q4]
                                    cmaps=["Blues",
                                           "Greens"
                                           None,                
                                           "coolwarm",
                                           "coolwarm_r"]

        Args:
            figsize (tuple, optional): plot size. Defaults to (16,16).
            nrows (int, optional): Total rows to divide the plot in. Defaults to 2.
            ncols (int, optional): Total cols to divide the plot in. Defaults to 2.
            titles (list, optional): List of titles. Pass in sequence as images. Length must be equal as images. Defaults to [].
            images (list, optional): Images to be plotted. Defaults to [].
            cmaps (list, optional): cmaps for images. Pass in sequence as images. Length must be equal as images. Defaults to [].
            show_colorbar (list, optional): list of bools. Pass in sequence as images. If True then colorbar will be displayed. Length must be equal as images. Defaults to [].
            fraction (float, optional): Colorbar related param. Defaults to 0.046.
            pad (float, optional): Colorbar related param. Defaults to 0.04.
        """
        
        import matplotlib.lines as mlines
        
        # * check for length mismatch
        if len(titles)!=len(images) or len(cmaps)!=len(images) or len(show_colorbar)!=len(images):
            print('Please provide titles, cmaps and show_colorbar list of same length as images list')
            return
        
        # * check if show_colorbar has all booleans
        total_bool=[True if isinstance(v,bool) else False for v in show_colorbar]
        if sum(total_bool)!=len(show_colorbar):
            print('Please give only bool values in "show_colorbar" list. Example: [True, False, False]')
            return

        
        # * replace all None by "gray"
        #// cmaps=[cmap if cmap is not None else 'gray' for cmap in cmaps]
        
        
        
        fig, axes = plt.subplots(
            nrows=nrows,
            ncols=ncols,
            # (nrows, ncols),
            figsize=figsize)
        
        axes = axes.flatten()
        
        for i in range(len(images)):
            
            img=axes[i].imshow(images[i], cmap=cmaps[i])
            axes[i].set_title(titles[i])
            
            # if len(legends[i]):
                # axes[i].legend(legends[i])
                
                # handles = []
                # for label in legends[i]:
                    # create an invisible artist with the label
                    # proxy = mlines.Line2D([], [], linestyle='none', label=label)
                    # handles.append(proxy)

                # axes[i].legend(
                #     # handles=handles,
                #     label=legends[i],
                #     loc="upper right")
                
            if show_colorbar[i]:
                fig.colorbar(
                    img,
                    ax=axes[i],
                    fraction=fraction,
                    pad=pad)
                
            axes[i].axis('off')
                
        plt.show()
        
#============================================================================================================================================   
    
    # > overall land stats (water, vegetation, unclassified) in percentage and area for lis4 sensor
    def lis4_over_all_land_stats(
        self,
        red_band:np.ndarray=None,
        green_band:np.ndarray=None,
        nir_band:np.ndarray=None,
        ndvi=None,
        ndwi=None,
        water_threshold:float=None,
        sensor:str="liss_4",
        area_unit:str="km2",
        band_auto_pick:bool=True,
        ):
        if band_auto_pick :
            red_band=self.extract_band(src_name='red')
            green_band=self.extract_band(src_name='green')
            nir_band=self.extract_band(src_name='nir')
            # swir_band=self.extract_band(src_name='swir')
            water_threshold=self.water_thresholds[sensor]
            
        elif (not band_auto_pick ) and (red_band is None or green_band is None or nir_band is None ):
                raise ValueError('please pass bands!')
            
            
        pixel_info = self.get_area_per_pixel(src_name='red')
        area_per_pixel={
                'area':pixel_info['pixel_area_km2'] if area_unit=='km2' else pixel_info['pixel_area_m2'],
                'unit':'km2' if area_unit=='km2' else 'm2'}
        
        
        if ndvi==None:
            ndvi=self.get_NDVI(
                            nir_band=nir_band,
                            red_band=red_band
                            )
        
        if ndwi==None:
            ndwi=self.get_NDWI(
                            nir_band=nir_band,
                            green_band=green_band
                            )
        
        veg_classified=self.classify_vegetation(
                                            ndvi=ndvi
                                            )
        
        water_mask,_=self.custom_mask(
                                index=ndwi,
                                threshold=water_threshold
                                )
        
        # * 0 represents bare land with no water, no vegetation, no built-up
        combined_mask=np.zeros_like(
                                ndvi
                                )
        
        # * put water
        combined_mask[water_mask]=1
        
        # * put vegetation
        combined_mask[veg_classified==3]=2
        combined_mask[veg_classified==4]=3
        
        
        total_size=combined_mask.size
        total_area=total_size*area_per_pixel['area']
        
        unclassified_ratio=np.round((np.sum(combined_mask==0)/total_size) * 100, 2)
        water_ratio=np.round((np.sum(combined_mask==1)/total_size) * 100, 2)
        moderate_veg_ratio=np.round((np.sum(combined_mask==2)/total_size) * 100, 2)
        dense_veg_ratio=np.round((np.sum(combined_mask==3)/total_size) * 100, 2)
        
        
        overall_land_stats_percent={
            "info":{
                'unclassified land':unclassified_ratio,
                'water coverage':water_ratio,
                'moderate vegetation coverage':moderate_veg_ratio,
                'dense vegetation coverage':dense_veg_ratio,
                },
            "unit": "%"
            }
        
        unclassified_area=round((np.sum(combined_mask==0) * area_per_pixel['area']),8)
        water_area=round((np.sum(combined_mask==1) * area_per_pixel['area']),8)
        moderate_veg_area=round((np.sum(combined_mask==2) * area_per_pixel['area']),8)
        dense_veg_area=round((np.sum(combined_mask==3) * area_per_pixel['area']),8)
    
        
        overall_land_stats_area={
            "info":{
                f'unclassified land area in {'km2' if area_unit=='km2' else 'm2'}':unclassified_area,
                f'water coverage area in {'km2' if area_unit=='km2' else 'm2'}':water_area,
                f'moderate vegetation coverage area in {'km2' if area_unit=='km2' else 'm2'}':moderate_veg_area,
                f'dense vegetation coverage area in {'km2' if area_unit=='km2' else 'm2'}':dense_veg_area,
                },
            "unit":area_per_pixel['unit']
            }
        
        stats_dir={
            f"total area in {'km2' if area_unit=='km2' else 'm2'}":total_area,
            "over all land cover %":overall_land_stats_percent,
            f"over all land cover in {area_per_pixel['unit']}":overall_land_stats_area
            }
        
        
        return combined_mask, stats_dir
          
#==============================================================================================================================================
    
    # > overall land stats (water, vegetation, built-up, unclassified) in percentage and area for sentinel, landsat and lis3 sensors
    def over_all_land_stats(
        self,
        red_band:np.ndarray=None,
        green_band:np.ndarray=None,
        nir_band:np.ndarray=None,
        swir_band:np.ndarray=None,
        ndvi=None,
        ndwi=None,
        ndbi=None,
        water_threshold:float=None,
        sensor:str=None,
        area_unit:str="km2",
        band_auto_pick:bool=True,
        ):
        """Combines all the indices as one mask. First calculates all the indices i.e. NDVI, NDBI, and NDWI. Then creates a water mask using a threshold --> classifies vegetation using self.classify_vegetation function --> classifies built-up using self.classify_builtup function. Creates a mask of all zeros of shape same as raster. zero represents unclassified/normal land. Then puts values in the following order: water ("1") --> moderate vegetation ("2") --> dense vegetation ("3") --> moderate built-up ("4") --> dense built-up ("5"). Where each thing is represented by the value inside the bracket.

        Args:
            red_band (np.ndarray, optional): red band. Defaults to None.
            green_band (np.ndarray, optional): green band. Defaults to None.
            nir_band (np.ndarray, optional): nir band. Defaults to None.
            swir_band (np.ndarray, optional): swir band. Defaults to None.
            water_threshold (float,optional): Threshold used to make water mask.
            sensor (str,optional): Sensor to which the bands belong to.
            band_auto_pick (bool, optional): If True then all the bands will be picked automatically from self.dataset. Defaults to True.

        Raises:
            ValueError: Either (band_auto_pick = True and sensor=any('sentinel', 'landsat', 'lis3', 'lis4')) or (all the bands (red, green, nir, swir) and water_threshold must be passed). If not then error will be raised.

        Returns:
            tuple: (combined mask, overall_land_stats dictionary)
        """
        
        if sensor in self.sensor_alias_names["liss_4"]:
            combined_mask, stats_dir = self.lis4_over_all_land_stats(
                red_band=red_band,
                green_band=green_band,
                nir_band=nir_band,
                ndvi=None,
                ndwi=None,
                water_threshold=None,
                # sensor:str="lis4",
                # area_unit:str="km2",
                band_auto_pick=True,)
            
            return combined_mask, stats_dir
        
        
        # if band_auto_pick and sensor in ['sentinel', 'landsat', 'lis3']:
        if band_auto_pick and sensor in self.sensor_alias_names['sentinel'] + self.sensor_alias_names['landsat'] + self.sensor_alias_names['liss_3']:
            red_band=self.extract_band(src_name='red')
            green_band=self.extract_band(src_name='green')
            nir_band=self.extract_band(src_name='nir')
            swir_band=self.extract_band(src_name='swir')
            water_threshold=self.water_thresholds[sensor]
            
        elif (not band_auto_pick or sensor is None) and (red_band is None or green_band is None or nir_band is None or swir_band is None):
                raise ValueError('please pass bands!')
            
            
        pixel_info = self.get_area_per_pixel(src_name='red')
        area_per_pixel={
                'area':pixel_info['pixel_area_km2'] if area_unit=='km2' else pixel_info['pixel_area_m2'],
                'unit':'km2' if area_unit=='km2' else 'm2'}
        
        if ndbi==None:    
            ndbi=self.get_NDBI(
                            swir_band=swir_band,
                            nir_band=nir_band
                            )
        if ndvi==None:
            ndvi=self.get_NDVI(
                            nir_band=nir_band,
                            red_band=red_band
                            )
        
        if ndwi==None:
            ndwi=self.get_NDWI(
                            nir_band=nir_band,
                            green_band=green_band
                            )
        
        veg_classified=self.classify_vegetation(
                                            ndvi=ndvi
                                            )
        built_classified=self.classify_builtup(
                                            ndbi=ndbi,
                                            sensor=sensor
                                            )
        water_mask,_=self.custom_mask(
                                index=ndwi,
                                threshold=water_threshold
                                )
        
        # * 0 represents bare land with no water, no vegetation, no built-up
        combined_mask=np.zeros_like(
                                ndvi
                                )
        
        # * put water
        combined_mask[water_mask]=1
        
        # * put vegetation
        combined_mask[veg_classified==3]=2
        combined_mask[veg_classified==4]=3
        
        # * put built-up
        combined_mask[built_classified==2]=4
        combined_mask[built_classified==3]=5
        
        total_size=combined_mask.size
        total_area=total_size*area_per_pixel['area']
        
        unclassified_ratio=np.round((np.sum(combined_mask==0)/total_size) * 100, 2)
        water_ratio=np.round((np.sum(combined_mask==1)/total_size) * 100, 2)
        moderate_veg_ratio=np.round((np.sum(combined_mask==2)/total_size) * 100, 2)
        dense_veg_ratio=np.round((np.sum(combined_mask==3)/total_size) * 100, 2)
        moderate_built_ratio=np.round((np.sum(combined_mask==4)/total_size) * 100, 2)
        dense_built_ratio=np.round((np.sum(combined_mask==5)/total_size) * 100, 2)
        
        overall_land_stats_percent={
            "info":{
                'unclassified land':unclassified_ratio,
                'water coverage':water_ratio,
                'moderate vegetation coverage':moderate_veg_ratio,
                'dense vegetation coverage':dense_veg_ratio,
                'moderate built-up coverage':moderate_built_ratio,
                'dense built-up coverage':dense_built_ratio
            },
            "unit": "%"
            }
        
        unclassified_area=round((np.sum(combined_mask==0) * area_per_pixel['area']),8)
        water_area=round((np.sum(combined_mask==1) * area_per_pixel['area']),8)
        moderate_veg_area=round((np.sum(combined_mask==2) * area_per_pixel['area']),8)
        dense_veg_area=round((np.sum(combined_mask==3) * area_per_pixel['area']),8)
        moderate_built_area=round((np.sum(combined_mask==4) * area_per_pixel['area']),8)
        dense_built_area=round((np.sum(combined_mask==5) * area_per_pixel['area']),8)
        
        overall_land_stats_area={
            "info":{
                f'unclassified land area in {'km2' if area_unit=='km2' else 'm2'}':unclassified_area,
                f'water coverage area in {'km2' if area_unit=='km2' else 'm2'}':water_area,
                f'moderate vegetation coverage area in {'km2' if area_unit=='km2' else 'm2'}':moderate_veg_area,
                f'dense vegetation coverage area in {'km2' if area_unit=='km2' else 'm2'}':dense_veg_area,
                f'moderate built-up coverage area in {'km2' if area_unit=='km2' else 'm2'}':moderate_built_area,
                f'dense built-up coverage area in {'km2' if area_unit=='km2' else 'm2'}':dense_built_area
                },
            "unit":area_per_pixel['unit']
            }
        
        stats_dir={
            f"total area in {'km2' if area_unit=='km2' else 'm2'}":total_area,
            "over all land cover %":overall_land_stats_percent,
            f"over all land cover in {area_per_pixel['unit']}":overall_land_stats_area
            }
        
        
        return combined_mask, stats_dir
        
#==============================================================================================================================================
    
    # > extract metadata from text file based on keywords
    def extract_metadata(
        self,
        path:str,
        keywords:list):
        
        # * Define the fields to extract
        fields_to_extract = keywords

        # * Dictionary to hold the extracted information
        info = {}

        # * Read and extract the required fields from the text file
        with open(path, 'r') as file:
            for line in file:
                
                line = line.strip()
                
                # * Only process lines containing '=' to avoid empty/invalid lines
                if '=' in line:
                    key, value = map(str.strip, line.split('=', 1))
                    if key in fields_to_extract:
                        info[key] = value
                        
        return info
    
#==============================================================================================================================================
    
    # > get location data using reverse_geocode
    def get_location_data(
        self,
        raster_path:str=None,
        bounds:tuple=None
        ):
        """Returns location data using reverse_geocode.

        Args:
            raster_path (str, optional): path of the raster image. Defaults to None.
            bounds (tuple, optional): bounds as (bottom, top, left, right). Defaults to None.

        Raises:
            ValueError: Bounds must be of length 4.
            ValueError: When a raster is not already only (self.dataset) then either bounds or the raster_path must be passed.

        Returns:
            dict: data about location such as country name, etc.
        """
        if raster_path==None and bounds==None:
            if len(self.dataset)==0:
                raise ValueError('No bands is opened, either open bands from a directory or pass one of the following [raster_path, bounds]')
            all_bands_names=list(self.dataset.keys())
            raster=self.dataset[all_bands_names[0]]
            
            bottom_coord=raster.bounds.bottom
            top_coord=raster.bounds.top
            left_coord=raster.bounds.left
            right_coord=raster.bounds.right
        
        elif bounds!=None and raster_path==None:
            if len(bounds)!=4:
                raise ValueError('bounds must have only 4 value pairs')
            left_coord,bottom_coord,right_coord,top_coord = bounds
            
        elif bounds==None and raster_path!=None:
            raster=rasterio.open(raster_path)
            
            bottom_coord=raster.bounds.bottom
            top_coord=raster.bounds.top
            left_coord=raster.bounds.left
            right_coord=raster.bounds.right
            
        else:
            raise ValueError("No bands are already opened! Either pass raster path or bounds")
            
        centre_coords=(bottom_coord + top_coord)/2, (left_coord + right_coord)/2

        geo_info=reverse_geocode.get(centre_coords)
        
        return geo_info
    
#==============================================================================================================================================

    # > get bounds of the raster in a dictionary format
    def get_bounds(self):
        
        bounds=self.dataset['red'].bounds
        
        image_bounds={
            'left': bounds.left,
            'bottom' : bounds.bottom,
            'right' : bounds.right,
            'top' : bounds.top
            }
        return image_bounds
        
#==============================================================================================================================================

    # > saves vegetation data for all AOIs as json in their respective directories
    def save_vegetation_data_all(
        self,
        sensor:str,
        parent_dir_path:str="default_path",
        output_dir_path:str="default_path",
        partition_nrows:int=3,
        partition_ncols:int=3,
        area_unit:str='km2',
        show_plot=False,
        start_from:int=0,
        run_for:int=-1
    ):
        
        if parent_dir_path=="default_path":
            if sensor.lower()=="sentinel" or sensor.lower()=="sentinel2" or sensor.lower()=="sentinel_2":
                parent_dir_path=self.default_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower()=="landsat" or sensor.lower()=="landsat9" or sensor.lower()=="landsat_9":
                parent_dir_path=self.default_parent_dir_path_dict["landsat"]
                
            elif sensor.lower()=="liss_3" or sensor.lower()=="liss3":
                parent_dir_path=self.default_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower()=="liss_4" or sensor.lower()=="liss4":
                parent_dir_path=self.default_parent_dir_path_dict["liss_4"]
                
        if output_dir_path=="default_path":
            if sensor.lower()=="sentinel" or sensor.lower()=="sentinel2" or sensor.lower()=="sentinel_2":
                output_dir_path=self.default_output_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower()=="landsat" or sensor.lower()=="landsat9" or sensor.lower()=="landsat_9":
                output_dir_path=self.default_output_parent_dir_path_dict["landsat"]
                
            elif sensor.lower()=="liss_3" or sensor.lower()=="liss3":
                output_dir_path=self.default_output_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower()=="liss_4" or sensor.lower()=="liss4":
                output_dir_path=self.default_output_parent_dir_path_dict["liss_4"]
            
            
        
        bands_dirs_list=os.listdir(parent_dir_path)
        
        run_for=len(bands_dirs_list) if run_for==-1 else start_from+run_for
        
        for bands_dir_name in bands_dirs_list[start_from:run_for]:
        # for bands_dir_name in bands_dirs_list:
            
            # * open sensor bands from directory
            bands_dir_path=os.path.join(
                parent_dir_path,
                bands_dir_name
                )
            
            aoi_output_dir=os.path.join(
                output_dir_path,
                bands_dir_name
            )
            os.makedirs(aoi_output_dir, exist_ok=True)
            
            self.open_band_from_dir(
                sensor=sensor,
                dir_path=bands_dir_path,
                )
            
            red_band=None
            nir_band=None
            
            if not self.dataset['red'].crs.is_projected:
                # * reproject bands to UTM
                self.reproject_to_UTM(src_name='red')
                self.reproject_to_UTM(src_name='nir')
            
                # * extract UTM bands
                red_band=self.extract_utm_band(src_name='red')
                nir_band=self.extract_utm_band(src_name='nir')
            
            else:
                red_band=self.extract_band(src_name='red')
                nir_band=self.extract_band(src_name='nir')
            
            # * calculate area/pixel
            pixel_info= self.get_area_per_pixel(src_name='red')
            area_per_pixel= pixel_info['pixel_area_km2'] if area_unit=='km2' else pixel_info['pixel_area_m2']
            
            # ================================================ ndvi calc =====================================================
            
            # * calculate NDVI
            ndvi=self.get_NDVI(
                nir_band=nir_band,
                red_band=red_band
                )
            
            # =============================================== plot ===========================================================
            
            if show_plot:
                # * create composite
                composite=self.create_composite(
                    pick_auto=True,
                    sensor=sensor
                    )
                
                # * classify vegetation based on thresholds
                whole_ndvi_classified_veg=self.classify_vegetation(ndvi=ndvi)
                
                # * plot composite, NDVI and classified vegetation
                self.plot_all_on_one(
                    nrows=1,
                    ncols=3,
                    figsize=(15,7),
                    titles=['composite','NDVI','NDVI classified'],
                    images=[composite,ndvi,whole_ndvi_classified_veg],
                    cmaps=[None,'coolwarm','Greens'],
                    show_colorbar=[False,True,True]
                    )
            
            # ============================================== cell wise data ================================================
            
            # * partition NDVI into cells
            partitions=self.make_cells(
                mask=ndvi,
                nrows=partition_nrows,
                ncols=partition_ncols
                )
            
            cell_veg_stats=dict()
            
            # * analyze each partition
            for i,p in enumerate(partitions,1):
                
                # * classify vegetation based on thresholds
                classified_veg=self.classify_vegetation(ndvi=p)
                
                
                # * calculate class metrics
                # //class_metrics_df=self.cal_class_metrics(classified_vals=classified_veg,classes=[1,2,3])
                
                
                # * compute global moran's I
                morans_i=self.compute_global_moran(p)
                
                
                # * calculate vegetation class coverage %
                veg_class_coverage_percent=self.vegetation_class_coverage_percent(classified_veg=classified_veg)
                
                
                # * calculate vegetation class coverage area
                veg_class_coverage_area=self.vegetation_class_coverage_area(
                    classified_veg=classified_veg,
                    pixel_area_km2= pixel_info['pixel_area_km2'] if area_unit=='km2' else None,
                    pixel_area_m2= pixel_info['pixel_area_m2'] if area_unit=='m2' else None
                    )
                
                # * calculate total cell area
                total_cell_area=p.size*area_per_pixel
                
                # * content for json
                cell_veg_stats[f'cell_{i}']={
                    f'total area covered by cell in {'km2' if area_unit=='km2' else 'm2'}': total_cell_area,
                    f"vegetation class coverage area in {'km2' if area_unit=='km2' else 'm2'}" : veg_class_coverage_area,
                    'vegetation class coverage %' : veg_class_coverage_percent,
                    'global morans I':morans_i
                    }
                
                # =============================================== prints =====================================================
                
                # * display results
                #// print(f'Global Moran\'s I: {morans_i}\n')
                #// print(f'Vegetation Class Coverage:\n{veg_class_coverage}\n')
                #// print(f'Class Metrics:\n{class_metrics_df}\n')
                
            print(cell_veg_stats)
            
            # =============================================== save in json =================================================
            
            
            
            self.save_in_json(
                content=cell_veg_stats,
                path=aoi_output_dir,
                file_name="veg_stats.json")
            
            print(f'saved veg stats for {bands_dir_name}')
            
#==============================================================================================================================================      
            
    # > saves water body data for all AOIs as json in their respective directories
    def save_water_data_all(
        self,
        sensor:str,
        parent_dir_path:str="default_path",
        output_dir_path:str="default_path",
        area_unit:str='m2',
        merge_distance_m=100,
        min_wb_area_m2=10000,
        show_plot=False,
        run_for:int=-1,
        start_from:int=0
        ):
    
        if parent_dir_path=="default_path":
            if sensor.lower()=="sentinel" or sensor.lower()=="sentinel2" or sensor.lower()=="sentinel_2":
                parent_dir_path=self.default_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower()=="landsat" or sensor.lower()=="landsat9" or sensor.lower()=="landsat_9":
                parent_dir_path=self.default_parent_dir_path_dict["landsat"]
                
            elif sensor.lower()=="liss_3" or sensor.lower()=="liss3":
                parent_dir_path=self.default_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower()=="liss_4" or sensor.lower()=="liss4":
                parent_dir_path=self.default_parent_dir_path_dict["liss_4"]
                
        if output_dir_path=="default_path":
            if sensor.lower()=="sentinel" or sensor.lower()=="sentinel2" or sensor.lower()=="sentinel_2":
                output_dir_path=self.default_output_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower()=="landsat" or sensor.lower()=="landsat9" or sensor.lower()=="landsat_9":
                output_dir_path=self.default_output_parent_dir_path_dict["landsat"]
                
            elif sensor.lower()=="liss_3" or sensor.lower()=="liss3":
                output_dir_path=self.default_output_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower()=="liss_4" or sensor.lower()=="liss4":
                output_dir_path=self.default_output_parent_dir_path_dict["liss_4"]
                
                
        bands_dirs_list=os.listdir(parent_dir_path)

        # for bands_dir_name in bands_dirs_list:
        
        run_for=len(bands_dirs_list) if run_for==-1 else start_from+run_for
        for bands_dir_name in bands_dirs_list[start_from:run_for]:
            
            # * open sensor bands from directory
            bands_dir_path=os.path.join(
                parent_dir_path,
                bands_dir_name)
            
            aoi_output_dir=os.path.join(
                output_dir_path,
                bands_dir_name
            )
            os.makedirs(aoi_output_dir, exist_ok=True)
            
            self.open_band_from_dir(
                sensor=sensor,
                dir_path=bands_dir_path,
                )
            
            # ====================================================================================================================
            green_band=None
            nir_band=None
            transform=None
            
            if not self.dataset['green'].crs.is_projected:
                # * reproject bands to UTM
                self.reproject_to_UTM(src_name='green')
                self.reproject_to_UTM(src_name='nir')
                
                # * extract UTM bands
                green_band=self.extract_utm_band(src_name='green')
                nir_band=self.extract_utm_band(src_name='nir')
                
                # * transform
                transform=self.utm_projected_data['green']['transform']
                
            else:
                green_band=self.extract_band(src_name='green')
                nir_band=self.extract_band(src_name='nir')
                transform=self.dataset['green'].transform
            
            # * create composite
            composite=self.create_composite(
                pick_auto=True,
                sensor=sensor)
            
            # * pixel info
            pixel_info=self.get_area_per_pixel(src_name='green')
            
            # =====================================================================================================================
            
            # * calculate NDWI
            ndwi=self.get_NDWI(
                nir_band=nir_band,
                green_band=green_band)
            
            # * create custom mask based on NDWI threshold
            ndwi_mask=self.make_water_mask(
                sensor=sensor,
                ndwi=ndwi)
            
            # * make kernel for morphological operations
            merge_distance = self.adaptive_merge_distance(
                pixel_size=np.sqrt(pixel_info['pixel_area_m2']),
                merge_distance_m=merge_distance_m           # * calculate kernel size based on pixel size and desired merge distance in meters
            )
            
            
            # * ndwi and ndwi combined mask with morphological operations
            ndwi_combined_poly=self.refine_water_mask(
                mask=ndwi_mask.astype(np.uint8)*255,      # * first convert to 8bit image
                pixel_area_m2=pixel_info['pixel_area_m2'],
                min_area_m2=min_wb_area_m2,
                merge_distance=merge_distance
                )
            
            # ===================================== segmenting, geo polygon generation ======================================

            # * segmentation
            seg,expands=self.segmentation_without_overlap(ndwi_combined_poly)

            # * geo polygons generation
            wb_poly_gdfs_dict=self.extract_polys_from_segs(
                expands,
                # transform=self.utm_projected_data['green']['transform'],
                transform=transform
                )

            # ================================================================================================================
            
            
            # =========================================== writing in json ====================================================
            
            water_bodies_info={}
            for wbn, gdf_lst in wb_poly_gdfs_dict.items():

                    poly_gdf,box_gdf = gdf_lst
                    
                    # * ignore background polygon
                    if wbn!='0':    
                        # * wb_area=poly_gdf.area
                        water_bodies_info[wbn]={
                            'bounding box':poly_gdf.iloc[0].geometry.bounds,
                            'area in m2':poly_gdf.iloc[0].geometry.area,
                            'unit':'m2'
                            }
                        
            
            self.save_in_json(
                content=water_bodies_info,
                path=aoi_output_dir,
                file_name="water_bodies_info.json")


            #  ================================================== plot =========================================================
            
            if show_plot:
                
                fig, axes=plt.subplots(1,3,figsize=(16,7))

                axes = axes.flatten()
                
                # image 1
                img1=axes[0].imshow(composite)
                axes[0].set_title('Composite RGB')
                axes[0].axis('off')
                fig.colorbar(img1, ax=axes[0], fraction=0.046, pad=0.04)

                # image 2
                img2=axes[1].imshow(ndwi,
                                    cmap='coolwarm_r')
                axes[1].set_title('NDWI')
                axes[1].axis('off')
                fig.colorbar(img2, ax=axes[1], fraction=0.046, pad=0.04)

                
                for wbn, gdf_lst in wb_poly_gdfs_dict.items():
                    
                    
                    poly_gdf,box_gdf = gdf_lst

                    poly_gdf.plot(ax=axes[2],
                                    color='lightblue',
                                    edgecolor='black',
                                    alpha=0.4)
                    
                    # * ignore background polygon
                    if wbn!='0':    
                        box_gdf.plot(ax=axes[2],
                                    color='red',
                                    edgecolor='white',
                                    alpha=0.2)

                        wb_area=poly_gdf.area

                axes[2].set_title(
                    "bounding boxes"
                    )
                axes[2].axis('off')

                fig.tight_layout()
                plt.show()
              
#==============================================================================================================================================
    
    # > saves built-up data for all AOIs as json in their respective directories
    def save_built_up_data_all(
        self,
        sensor:str,
        parent_dir_path:str="default_path",
        output_dir_path:str="default_path",
        partition_nrows:int=3,
        partition_ncols:int=3,
        area_unit:str='km2',
        show_plot=False,
        run_for:int=-1,
        start_from:int=0
        
    ):
        
        if parent_dir_path=="default_path":
            if sensor.lower()=="sentinel" or sensor.lower()=="sentinel2" or sensor.lower()=="sentinel_2":
                parent_dir_path=self.default_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower()=="landsat" or sensor.lower()=="landsat9" or sensor.lower()=="landsat_9":
                parent_dir_path=self.default_parent_dir_path_dict["landsat"]
                
            elif sensor.lower()=="liss_3" or sensor.lower()=="liss3":
                parent_dir_path=self.default_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower()=="liss_4" or sensor.lower()=="liss4":
                parent_dir_path=self.default_parent_dir_path_dict["liss_4"]
                
        if output_dir_path=="default_path":
            if sensor.lower()=="sentinel" or sensor.lower()=="sentinel2" or sensor.lower()=="sentinel_2":
                output_dir_path=self.default_output_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower()=="landsat" or sensor.lower()=="landsat9" or sensor.lower()=="landsat_9":
                output_dir_path=self.default_output_parent_dir_path_dict["landsat"]
                
            elif sensor.lower()=="liss_3" or sensor.lower()=="liss3":
                output_dir_path=self.default_output_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower()=="liss_4" or sensor.lower()=="liss4":
                output_dir_path=self.default_output_parent_dir_path_dict["liss_4"]
                
        bands_dirs_list=os.listdir(parent_dir_path)

        # for bands_dir_name in bands_dirs_list:
        run_for=len(bands_dirs_list) if run_for==-1 else start_from+run_for
        
        for bands_dir_name in bands_dirs_list[start_from:run_for]:
            
            # * open sensor bands from directory
            bands_dir_path=os.path.join(parent_dir_path,bands_dir_name)
            aoi_output_dir=os.path.join(output_dir_path,bands_dir_name)
            os.makedirs(aoi_output_dir, exist_ok=True)
            
            self.open_band_from_dir(
                sensor=sensor,
                dir_path=bands_dir_path,
                )
            
            if not self.dataset['nir'].crs.is_projected:
                # * reproject bands to UTM
                self.reproject_to_UTM(src_name='swir')
                self.reproject_to_UTM(src_name='nir')
                
                # * extract UTM bands
                swir_band=self.extract_utm_band(src_name='swir')
                nir_band=self.extract_utm_band(src_name='nir')
            
            else:
                swir_band=self.extract_band(src_name='swir')
                nir_band=self.extract_band(src_name='nir')
            
            pixel_info=self.get_area_per_pixel(src_name='nir')
            area_per_pixel= pixel_info['pixel_area_km2'] if area_unit=='km2' else pixel_info['pixel_area_m2']
            
            # ========================================================== calc ndbi ===================================================
            
            # * calculate NDBI
            ndbi=self.get_NDBI(nir_band=nir_band,
                            swir_band=swir_band)
            
            # ========================================================= cell wise data ================================================
            
            
            # * partition NDBI into 3x3 cells
            partitions=self.make_cells(
                mask=ndbi,
                nrows= partition_nrows,
                ncols= partition_ncols)
            
            cell_built_stats=dict()
            
            # * analyze each partition
            for i,p in enumerate(partitions,1):
                
                # * classify built-up based on thresholds
                classified_built_up=self.classify_builtup(
                    ndbi=p,
                    sensor=sensor
                    )
                # if sensor=='lis3':
                #     classified_built_up=self.classify_lis3_builtup(ndbi=p)
                    
                # else:
                #     classified_built_up=self.classify_builtup(ndbi=p)
                
                # * calculate class metrics
                #// class_metrics_df=self.cal_class_metrics(classified_vals=classified_built_up,classes=[1,2,3])
                
                # * calculate built-up class coverage percent
                built_up_class_coverage_percent=self.built_up_class_coverage_percent(classified_builtup=classified_built_up)
                
                # * calculate built-up class coverage area
                # built_up_class_coverage_area= self.built_up_class_coverage_area(
                #     classified_builtup=classified_built_up,
                #     pixel_area_km2= pixel_info['pixel_area_km2'] if area_unit=='km2' else None,
                #     pixel_area_m2= pixel_info['pixel_area_m2'] if area_unit=='m2' else None
                #     )
                
                # * calculate total cell area
                total_cell_area=p.size*area_per_pixel
                
                cell_built_stats[f'cell_{i}']={
                    f'total area covered by cell in {'km2' if area_unit=='km2' else 'm2'}':total_cell_area,
                    # f'built-up class coverage area in {'km2' if area_unit=='km2' else 'm2'}':built_up_class_coverage_area,
                    'built-up class coverage %':built_up_class_coverage_percent,
                    }
                
                # * display results
                #// print(f'built-up Class Coverage:\n{built_up_class_coverage}\n')
                #// print(f'Class Metrics:\n{class_metrics_df}\n')
                
                
            print(cell_built_stats)
            
            # ======================================================= save as json =====================================================
            
            self.save_in_json(
                content=cell_built_stats,
                path=aoi_output_dir,
                file_name="built_up_stats.json")
            
            print(f'saved built-up stats for {bands_dir_name}')
            
            # ========================================================== plot =======================================================
            
            if show_plot:
            # * create composite
                composite=self.create_composite(
                    pick_auto=True,
                    sensor=sensor
                    )
                
                # * classify built-up based on thresholds
                # whole_ndbi_classified=self.classify_builtup(ndbi=ndbi)
                # if sensor=='lis3':
                #     whole_ndbi_classified=self.classify_lis3_builtup(ndbi=ndbi)
                    
                # else:
                #     whole_ndbi_classified=self.classify_builtup(ndbi=ndbi)
                whole_ndbi_classified=self.classify_builtup(
                    ndbi=ndbi,
                    sensor=sensor,
                    )
                
                # * plot composite, NDBI and classified built-up
                self.plot_all_on_one(
                    nrows=1,
                    ncols=3,
                    figsize=(15,7),
                    titles=['composite','NDBI','NDBI classified'],
                    images=[composite,ndbi,whole_ndbi_classified],
                    cmaps=[None,'coolwarm','Greens'],
                    show_colorbar=[False,True,True]
                    )
              
              
    def save_overall_landstats(
        self,
        sensor:str,
        parent_dir_path:str="default_path",
        output_dir_path:str="default_path",
        start_from:int=0,
        run_for:int=-1,
        print_overall_land_stats:bool=False,
        show_plot:bool=False
    ):
        
        if parent_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                parent_dir_path=self.default_parent_dir_path_dict["sentinel"]
            
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                parent_dir_path=self.default_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_4"]
                
        if output_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                output_dir_path=self.default_output_parent_dir_path_dict["sentinel"]
            
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                output_dir_path=self.default_output_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_4"]
        
        bands_dirs_list=os.listdir(parent_dir_path)

        run_for=len(bands_dirs_list) if run_for==-1 else start_from+run_for
        for bands_dir_name in bands_dirs_list[start_from:run_for]:
            
            bands_dir_path=os.path.join(
                parent_dir_path,
                bands_dir_name)
            
            aoi_output_dir=os.path.join(
                output_dir_path,
                bands_dir_name
            )
            os.makedirs(aoi_output_dir, exist_ok=True)
            
            self.open_band_from_dir(
                dir_path=bands_dir_path,
                sensor=sensor
            )
            
            overall_land_mask, over_all_land_stats  = self.over_all_land_stats(
                band_auto_pick=True,
                sensor=sensor
            )
            
            if print_overall_land_stats:
                print(over_all_land_stats)
                
            if show_plot:
                cmp_img=self.create_composite(
                    pick_auto=True,
                    sensor=sensor
                    )
                self.plot_all_on_one(
                    nrows=1,
                    ncols=2,
                    titles=["composite","Overall land cover"],
                    images=[cmp_img,overall_land_mask],
                    cmaps=[None,'tab20'],
                    legends=[[],['unclassified land','water','moderate vegetation','dense vegetation','moderate built-up','dense built-up']],
                    show_colorbar=[False,False]
                )
            
            self.save_in_json(
                content=over_all_land_stats,
                path=aoi_output_dir,
                file_name="overall_land_stats.json"
                )
    
#==============================================================================================================================================
    
    # > converts ndarray to jpg and saves it in the given path if jpg_path is not empty
    def ndarray_to_jpg(
        self,
        ndarray,
        # jpg_path:str=''
        output_dir_path:str,
        file_name:str,
        ):
        
        lower, upper = ndarray.min(), ndarray.max()
        
        # Normalize to 0–255 range
        # img = (255 * (ndarray - lower) / (upper - lower)).astype(np.uint8)
        
        lower, upper = np.nanmin(ndarray), np.nanmax(ndarray)
        img_float = 255 * (ndarray - lower) / (upper - lower + 1e-10)

        # Replace NaNs (invalid pixels) with zero
        img_float = np.nan_to_num(img_float, nan=0.0)

        img = img_float.astype(np.uint8)
        
        # Handle grayscale vs RGB
        if img.ndim == 2:
            pil_img = Image.fromarray(img, mode="L")  # Grayscale
        elif img.ndim == 3 and img.shape[2] == 3:
            pil_img = Image.fromarray(img, mode="RGB")  # RGB
        elif img.ndim == 3 and img.shape[2] == 4:
            pil_img = Image.fromarray(img, mode="RGBA")  # RGBA
        else:
            raise ValueError(f"Unsupported array shape: {img.shape}")

        # if jpg_path!='':
        #     pil_img.save(jpg_path, quality=100)
        #     print(f"Saved: {jpg_path}")
        # # print('no image is saved, uncomment the code first!')
        
        if output_dir_path!='':
            os.makedirs(output_dir_path, exist_ok=True)
            jpg_full_path = os.path.join(output_dir_path, file_name)
            pil_img.save(jpg_full_path, quality=100)
            print(f"Saved: {jpg_full_path}")
            
        return pil_img  
    
#==============================================================================================================================================

    # > saves UTM projected composite jpg in each AOI directory
    def save_UTM_projected_jpg(
        self,
        sensor:str,
        parent_dir_path:str="default_path",
        output_dir_path:str="default_path",
        run_for:int=-1,
        start_from:int=0
    ):
        
        if parent_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                parent_dir_path=self.default_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                parent_dir_path=self.default_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_4"]
                
        if output_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                output_dir_path=self.default_output_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                output_dir_path=self.default_output_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_4"]
                
                
        order=[]
        if sensor.lower() in self.sensor_alias_names["sentinel"]:
            order=['red','green','blue']
        elif sensor.lower() in self.sensor_alias_names["landsat"]:
            order=['red','green','blue']
        elif sensor.lower() in self.sensor_alias_names["liss_3"]:
            order=['swir','nir','red']
        elif sensor.lower() in self.sensor_alias_names["liss_4"]:
            order=['nir','red','green']
            
        bands_dirs_list=os.listdir(parent_dir_path)

        run_for=len(bands_dirs_list) if run_for==-1 else start_from+run_for
        
        for bands_dir_name in bands_dirs_list[start_from:run_for]:
            

        # for sensor_name,parent_dir_path in parent_dir_paths.items():
            
            
            
            # bands_dirs_names=os.listdir(parent_dir_path)
            
        # for bands_dir_name in bands_dirs_names:
            
            bands_dir_path=os.path.join(
                parent_dir_path,
                bands_dir_name
                )
            
            aoi_output_dir=os.path.join(
                output_dir_path,
                bands_dir_name
            )
            os.makedirs(aoi_output_dir, exist_ok=True)
            
            self.open_band_from_dir(
                sensor=sensor.lower(),
                dir_path=bands_dir_path,
                )
            
            red_band=None
            blue_band=None
            green_band=None
            nir_band=None
            swir_band=None
            
                
            if not self.dataset['red'].crs.is_projected:
            # * reproject bands to UTM
            
                self.reproject_to_UTM(src_name='red')    
                red_band=self.extract_utm_band(src_name='red')
                
                # * if sensor is sentinel or landsat or liss4, reproject green and blue bands to UTM
                if sensor.lower() in self.sensor_alias_names["sentinel"] + self.sensor_alias_names["landsat"] + self.sensor_alias_names["liss_4"]:
                    self.reproject_to_UTM(src_name='green')
                    green_band=self.extract_utm_band(src_name='green')
                    
                    if sensor.lower() in self.sensor_alias_names["sentinel"] + self.sensor_alias_names["landsat"]:
                        self.reproject_to_UTM(src_name='blue')
                        blue_band=self.extract_utm_band(src_name='blue')
                    
                # * if sensor is liss3, reproject nir and swir bands to UTM
                if sensor.lower() in self.sensor_alias_names["liss_3"] + self.sensor_alias_names["liss_4"]:
                    self.reproject_to_UTM(src_name='nir')
                    nir_band=self.extract_utm_band(src_name='nir')
                
                    if sensor.lower() in self.sensor_alias_names["liss_3"]:
                        self.reproject_to_UTM(src_name='swir')
                        swir_band=self.extract_utm_band(src_name='swir')
                
        
            else:   
    
                red_band=self.extract_band(src_name='red')
                
                if sensor.lower() in self.sensor_alias_names["sentinel"] + self.sensor_alias_names["landsat"] + self.sensor_alias_names["liss_4"]:
                    green_band=self.extract_band(src_name='green')
                    
                    if sensor.lower() in self.sensor_alias_names["sentinel"] + self.sensor_alias_names["landsat"]:
                        blue_band=self.extract_band(src_name='blue')
                    
                if sensor.lower() in self.sensor_alias_names["liss_3"] + self.sensor_alias_names["liss_4"]:
                    nir_band=self.extract_band(src_name='nir')
                
                    if sensor.lower() in self.sensor_alias_names["liss_3"]:
                        swir_band=self.extract_band(src_name='swir')
            
            if sensor.lower() in self.sensor_alias_names["sentinel"] + self.sensor_alias_names["landsat"]:
                bands_dict={
                    'red':red_band,
                    'green':green_band,
                    'blue':blue_band
                }
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                bands_dict={
                    'swir':swir_band,
                    'nir':nir_band,
                    'red':red_band
                }
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                bands_dict={
                    'nir':nir_band,
                    'red':red_band,
                    'green':green_band
                }
                
                
            composite=self.create_composite(
                sensor=sensor.lower(),
                bands=bands_dict,
                order=order
                )
            
            # self.plot_raster(composite)
            # print(self.extract_band(src_name='red').shape,composite.shape)
            
            # self.ndarray_to_jpg(
            #     ndarray=composite,
            #     jpg_path=os.path.join(
            #         aoi_output_dir,
            #         f'{bands_dir_name}.jpg'
            #         )
            # )
            
            self.ndarray_to_jpg(
                ndarray=composite,
                output_dir_path=aoi_output_dir,
                file_name=f'{bands_dir_name}.jpg',
                )
                
#==============================================================================================================================================        
            
    # > saves spatial metadata such as CRS, pixel resolution, pixel area, etc. for all AOIs as json in their respective directories
    def save_spatial_data(
        self,
        sensor:str,
        parent_dir_path:str="default_path",
        output_dir_path:str="default_path",
        start_from:int=0,
        run_for:int=-1
        ):
        
        if parent_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                parent_dir_path=self.default_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                parent_dir_path=self.default_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_4"]
                
        if output_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                output_dir_path=self.default_output_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                output_dir_path=self.default_output_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_4"]
                
        
        bands_dirs_list=os.listdir(parent_dir_path)

        run_for=len(bands_dirs_list) if run_for==-1 else start_from+run_for
        
        for bands_dir_name in bands_dirs_list[start_from:run_for]:
            
            # * open sensor bands from directory
            bands_dir_path=os.path.join(
                parent_dir_path,
                bands_dir_name
                )
            
            aoi_output_dir = os.path.join(
                output_dir_path,
                bands_dir_name
                )
            
            os.makedirs(aoi_output_dir, exist_ok=True)
            
            self.open_band_from_dir(
                sensor=sensor,
                dir_path=bands_dir_path,
                )
            
            crs=None
            transform=None
            
            if not self.dataset['red'].crs.is_projected:
            # * reproject bands to UTM
                self.reproject_to_UTM(src_name='red')
                crs = self.utm_projected_data['red']['profile']['crs']
                # Extract resolution / pixel sizes
                transform=self.utm_projected_data['red']['transform']
                
            else:
                crs=self.dataset['red'].crs
                transform = self.dataset['red'].transform
            
            
            crs_name = crs.to_string()  # e.g. 'EPSG:32645'

            pixel_width = abs(transform.a)
            pixel_height = abs(transform.e)

            # Compute pixel area (meters² for projected)
            pixel_area = pixel_width * pixel_height

            spatial_metadata_dict={
                "Coordinate system type":"Projected",
                "CRS name": crs_name,
                "Units":"meters",
                "Pixel resolution":{"width_meters":round(pixel_width,2),"height_meters":round(pixel_height,2)},
                "Pixel area (square meters per pixel)":round(pixel_area,2),
                "Pixel area is uniform across the image":True
            }
            
            self.save_in_json(
                content=spatial_metadata_dict,
                path=aoi_output_dir,
                file_name="spatial_metadata.json"
            )
            
    def save_location_info(
        self,
        sensor:str,
        parent_dir_path:str="default_path",
        output_dir_path:str="default_path",
        start_from:int=0,
        run_for:int=-1
        ):

        if parent_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                parent_dir_path=self.default_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                parent_dir_path=self.default_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_4"]
                
                
        if output_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                output_dir_path=self.default_output_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                output_dir_path=self.default_output_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_4"]
        
        bands_dirs_list=os.listdir(parent_dir_path)

        run_for=len(bands_dirs_list) if run_for==-1 else start_from+run_for
        for bands_dir_name in bands_dirs_list[start_from:run_for]:
            
            bands_dir_path=os.path.join(
                parent_dir_path,
                bands_dir_name)
            
            aoi_output_dir=os.path.join(
                output_dir_path,
                bands_dir_name
            )
            
            os.makedirs(aoi_output_dir, exist_ok=True)
            
            self.open_band_from_dir(
                dir_path=bands_dir_path,
                sensor=sensor
            )
            
            location_info=self.get_location_data()
            
            self.save_in_json(
                content=location_info,
                path=aoi_output_dir,
                file_name="location_info.json"
            )
            
    def save_image_bounds(
        self,
        sensor,
        parent_dir_path:str="default_path",
        output_dir_path:str="default_path",
        start_from:int=0,
        run_for:int=-1
        ):
        
        if parent_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                parent_dir_path=self.default_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                parent_dir_path=self.default_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                parent_dir_path=self.default_parent_dir_path_dict["liss_4"]
                
                
        if output_dir_path=="default_path":
            if sensor.lower() in self.sensor_alias_names["sentinel"]:
                output_dir_path=self.default_output_parent_dir_path_dict["sentinel"]
                
            elif sensor.lower() in self.sensor_alias_names["landsat"]:
                output_dir_path=self.default_output_parent_dir_path_dict["landsat"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_3"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_3"]
                
            elif sensor.lower() in self.sensor_alias_names["liss_4"]:
                output_dir_path=self.default_output_parent_dir_path_dict["liss_4"]
        
        bands_dirs_list=os.listdir(parent_dir_path)

        run_for=len(bands_dirs_list) if run_for==-1 else start_from+run_for
        for bands_dir_name in bands_dirs_list[start_from:run_for]:
            
            bands_dir_path=os.path.join(
                parent_dir_path,
                bands_dir_name)
            
            aoi_output_dir=os.path.join(
                output_dir_path,
                bands_dir_name
            )
            
            os.makedirs(aoi_output_dir, exist_ok=True)
            
            self.open_band_from_dir(
                dir_path=bands_dir_path,
                sensor=sensor
            )
            

            
            self.save_in_json(
                content=self.get_bounds(),
                path=aoi_output_dir,
                file_name="bounds.json"
            )
    


