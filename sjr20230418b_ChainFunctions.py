# %%
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import nd2
import os

## Display Options
BASE_SCALE = 500
MIN_QUANTILE = 0
MAX_QUANTILE = 0.995
COLOR_ASSIGNMENT = {'Cy5' : 'r',
                    647 : 'r',
                    488 : 'g',
                    'FITC' : 'g',
                    'FITC WF' : 'g',
                    405 : 'b'}

# %%
def master():
    global selectedMeta, filePaths
    filePaths = filedialog.askopenfilenames(filetypes=[("ND2 files", "*.nd2"), ("All files", "*.*")])
    if filePaths == '':
        winUpload.quit()
        return
    if len(filePaths) != 2: 
        messagebox.showwarning('Error',f'2 files required, {len(filePaths)} selected')
        raise ValueError(f'2 images required, {len(filePaths)} selected')
    selectedMeta = (image_metdata(filePaths[0]), image_metdata(filePaths[1]))
    scaledImages = image_scale(filePaths=filePaths, metadata=selectedMeta)
    image_display(scaledImages[0], filePaths[0], 0)
    image_display(scaledImages[1], filePaths[1], 1)
    # winUpload.quit()

def rerunzero(combobox):
    idxFOV0 = int(varFOV0.get())-1
    inputImageRerun = image_prepare(filePaths[0], selectedMeta[0], idx=0, selectedPlane=idxFOV0)
    outputImageRerun = inputImageRerun.resize((BASE_SCALE,BASE_SCALE), Image.LANCZOS)
    image_display(outputImageRerun, filePaths[0], idx=0)

def rerunone(combobox):
    idxFOV1 = int(varFOV1.get())-1
    inputImageRerun = image_prepare(filePaths[1], selectedMeta[1], idx=1, selectedPlane=idxFOV1)
    outputImageRerun = inputImageRerun.resize((ratScaleImages,ratScaleImages), Image.LANCZOS)
    image_display(outputImageRerun, filePaths[1], idx=1)

def image_metdata(filePath:str) -> dict:
    '''
    Returns scale and c, z, and p dimensions for nd2 file at the specified file path.
    Extracts scale as µm/pixel of x-axis of first color channel, thus assumes that x and y
    scales are identical for all c, z, and p.
    '''
    meta = {}

    with nd2.ND2File(filePath) as ndFile:
        meta['names'] = [int(c.channel.name) if c.channel.name.isdigit() else c.channel.name for c in ndFile.metadata.channels] # type: ignore
        meta['pseudos'] = [pseudocolor_from_name(n) for n in meta['names']]
        meta['scale'] = ndFile.metadata.channels[0].volume.axesCalibration[0] # type: ignore
        meta['c'] = ndFile.sizes.get('C', 0)
        meta['z'] = ndFile.sizes.get('Z', 0)
        meta['p'] = ndFile.sizes.get('P', 0)
    return meta

def pseudocolor_from_name(name:str|int) -> str:
    pc = ''
    if name in COLOR_ASSIGNMENT: return COLOR_ASSIGNMENT[name]
    try:
        if name <= 495: pc = 'b' # type: ignore
        if name <= 590: pc = 'g' # type: ignore
        if name > 590: pc = 'r' # type: ignore
        messagebox.showwarning('Warning',f'Unrecognized color "{name}," assumed to be wavelength and displaying as {pc.upper()}')
    except TypeError:
        messagebox.showerror('Error',f'Unrecognized color not interpretable as a wavelength: "{name}." Displaying as B, please update COLOR_ASSIGNMENT variable.')
        # raise ValueError(f'Unrecognized color and not interpretable as a wavelength: "{name}." Update COLOR_ASSIGNMENT variable.')
    if pc == '': pc = 'b'
    return pc

def image_scale(filePaths:tuple[str,str], metadata:tuple[dict, dict]) -> tuple[Image.Image,Image.Image]:
    global ratScaleImages
    
    # make list of scales
    scales = [image['scale'] for image in metadata]
    
    # find largest scale and ratio between scales
    if scales[0] == scales[1]: # could instead use if scale0>scale1 resize image1, else resize image0
        maxScale = scales[0]
        idxMax = 0
        minScale = scales[1]
        idxMin = 1
    else: # scales[0] != scales[1]:
        maxScale = max(scales)
        idxMax = scales.index(maxScale)
        minScale = min(scales)
        idxMin = scales.index(minScale)
    ratScaleImages = int(round(BASE_SCALE * (minScale / maxScale), 0))

    # display largest scale image at static size
    inputImageMax = image_prepare(filePaths[idxMax], metadata[idxMax], idxMax)
    # ratScaleAxes = int(round(inputImageMax.height/(inputImageMax.width/BASE_SCALE),0)) # an initial attempt at accounting for rectangular images
    outputImageMax = inputImageMax.resize((BASE_SCALE,BASE_SCALE), Image.LANCZOS) # add support for rectangular images using a ratio of og dimensions instead of a constant value? XXX
    
    # display smaller image scaled down appropriately
    inputImageMin = image_prepare(filePaths[idxMin], metadata[idxMin], idxMin)
    outputImageMin = inputImageMin.resize((ratScaleImages,ratScaleImages), Image.LANCZOS) # LANCZOS filter performs weighted average of neighboring pixels using truncated sinc function
    
    return (outputImageMax,outputImageMin)

def image_prepare(filePath:str, metadata:dict, idx:int, selectedPlane:int=0) -> Image.Image:
    '''Get image ready for scaling (max project or select FOV, normalize)'''
    
    ndArray = nd2.imread(filePath) # type: ignore
    arrReduced = ndArray # set here and then possibly overwritten

    if metadata['z']:
        arrReduced = z_max_project(ndArray)

    if metadata['p']:
        arrReduced = arrReduced[selectedPlane]
        noOfPlanes = int(metadata['p']+1)
        # create combo box to pick FOV
        if idx == 0:
            comFOV0.bind('<<ComboboxSelected>>', rerunzero)
            comFOV0['values'] = tuple(range(1, noOfPlanes))
            comFOV0.current(selectedPlane)
            comFOV0.grid(row=3, column=1, sticky='w')
            labPrompt0.grid(row=3, column=0, sticky='e')
        elif idx == 1:
            comFOV1.bind('<<ComboboxSelected>>', rerunone)
            comFOV1['values'] = tuple(range(1, noOfPlanes))
            comFOV1.current(selectedPlane)
            comFOV1.grid(row=3, column=3, sticky='w')
            labPrompt1.grid(row=3, column=2, sticky='e')
    else:
        for widget in comFOV0, labPrompt0, comFOV1, labPrompt1:
            if widget.winfo_ismapped: 
                widget.grid_forget()

    imgMerge = image_merge(array=arrReduced, noOfColors=metadata['c'], pseudocolors=metadata['pseudos'])

    return imgMerge
    

def z_max_project(ndArray:np.ndarray) -> np.ndarray:
    '''nd2.imread() returns dimensions as (z,c,x,y) so this function creates a max projection along the z-axis'''
    return np.max(ndArray, axis=0)

def image_merge(array:np.ndarray, noOfColors:float, pseudocolors:list[str]) -> Image.Image:
    imageBands = {'r' : None,
                    'g' : None,
                    'b' : None
                    }

    for channel in range(int(noOfColors)):
        color = pseudocolors[channel]
        imageBands[color] = image_normalization(arrReduced=array, colorChannel=channel) # type: ignore
    
    if any(color is None for color in imageBands.values()):
        tempTrueImage = next((color for color in imageBands.values() if color),None)
        if not tempTrueImage: raise ValueError('No valid color bands')
        for color in imageBands:
            imageBands[color] = imageBands[color] if imageBands[color] else Image.new('L', tempTrueImage.size, 0) # type: ignore

    imgMerge = Image.merge('RGB', (imageBands['r'],imageBands['g'],imageBands['b'])) # type: ignore
    return imgMerge

def image_normalization(arrReduced:np.ndarray, colorChannel:int) -> Image.Image:
    arrTemp = arrReduced[colorChannel].astype(float)
    
    ## this simply noramlizes to the min and max values
    # maxPixel = np.max(arrTemp)
    # minPixel = np.min(arrTemp)
    # arrNorm = np.uint8((arrTemp-minPixel)/(maxPixel-minPixel)*255)

    ## this normalizes to specified quantiles, without using if statements (h/t BP Bratton)
    minPixel = np.quantile(arrTemp, MIN_QUANTILE)
    maxPixel = np.quantile(arrTemp, MAX_QUANTILE)

    arrNorm = (arrTemp-minPixel)
    arrNorm = (arrNorm + np.sqrt(arrNorm**2)) / 2
    
    arrNorm = arrNorm/(maxPixel-minPixel)
    arrNormB = 1 - arrNorm
    arrNormB = (arrNormB + np.sqrt(arrNormB**2)) / 2
    arrNorm = 1 - arrNormB
    arrNorm = (arrNorm*255).astype(np.uint8)
    
    imgPil = Image.fromarray(arrNorm)
    return imgPil

def image_display(scaledImage:Image.Image, filePath:str, idx:int):
    # global photoImage, labImage # this line may be necessary later
    
    titleImage = f'titleImage{idx}'
    labTitle = f'labTitle{idx}'
    photoImage = f'photoImage{idx}'
    labImage = f'labImage{idx}'

    ### first image
    # create and place title
    globals()[titleImage] = os.path.splitext(os.path.basename(filePath))[0]
    globals()[labTitle].grid(row=1, column=2*idx, columnspan=2)
    globals()[labTitle].config(text=eval(titleImage))
    # labTitle0.text = titleImage0 # unsure if line will be necessary

    # create and place PhotoImage
    globals()[photoImage] = ImageTk.PhotoImage(image=scaledImage)
    globals()[labImage].grid(row=2, column=2*idx, columnspan=2)
    globals()[labImage].config(image=eval(photoImage))
    globals()[labImage].image = eval(photoImage)

    # ### second image
    # # create and place title
    # titleImage1 = os.path.splitext(os.path.basename(filePaths[1]))[0]
    # labTitle1.config(text=titleImage1)
    # # labImage1.text = titleImage1

    # # create and place PhotoImage
    # photoImage1 = ImageTk.PhotoImage(image=scaledImages[1])
    # labImage1.config(image=photoImage1)
    # labImage1.image = photoImage1

# %%
### create window and widgets

## window
winUpload = tk.Tk()
winUpload.title('Image comparison utility')

## upload button
btnUpload = tk.Button(text='Select 2 images', command=master) #())
btnUpload.grid(column=0, row=0, sticky='nw')

## labels for images, titles, and comboboxes
# left
labTitle0 = tk.Label(winUpload, text='zero')#, text=nameImage0)
labImage0 = tk.Label(winUpload)
varFOV0 = tk.StringVar()
comFOV0 = ttk.Combobox(winUpload, textvariable=varFOV0, width=2, state='readonly')
labPrompt0 = tk.Label(winUpload, text='Plane/FOV:')

# right
labTitle1 = tk.Label(winUpload, text='one')#, text=nameImage1)
labImage1 = tk.Label(winUpload)
varFOV1 = tk.StringVar()
comFOV1 = ttk.Combobox(winUpload, textvariable=varFOV1, width=3, state='readonly')
labPrompt1 = tk.Label(winUpload, text='Plane/FOV:')


winUpload.mainloop()

#####
# Next steps: 
# 3. create scalebar
# 4. Take clicks from image scalebars?
# 8. Improve image_merge variables
