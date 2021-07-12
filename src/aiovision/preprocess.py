from PIL import Image, UnidentifiedImageError
import os, tempfile, PyPDF2, shutil

def is_file_like(f):
    return hasattr(f,"read") and hasattr(f,"write") and hasattr(f,"seek")

def is_usable_as_file(f):
    return isinstance(f, (str, bytes, os.PathLike)) or is_file_like(f)

def convert_image_to_pdf(f, save_to):
    try:
        Image.open(f).save(save_to, "pdf")
    except UnidentifiedImageError:
        #Makes sure that this is a pdf, that there is a page, and that the pdf isn't encrypted
        #If not, fail loudly (would throw a PyPDF2.utils.PdfReadError if there is an error)
        if PyPDF2.PdfFileReader(f).getNumPages():
            #Data duplication is better than data loss
            if is_file_like(f):
                shutil.copyfileobj(f, save_to)
            else:
                with open(f,"rb") as f_asfile:
                    shutil.copyfileobj(f_asfile, save_to)
        else:
            #Yes, this really can happen
            #To make one, pass preprocess an empty list and a path to save to -> preprocess([],"empty.pdf")
            #It will complete without any errors.
            #Now try passing that file back into preprocess -> preprocess("empty.pdf","some_other_name.pdf")
            raise ValueError("Received an invalid pdf with zero pages!")

    
    #Gotta make sure you can use this in a list comp, right?
    #I also don't want to accidentally close the source file handle
    #because that might result in data loss (like with a temp file)
    return save_to

#This function can throw (at least) the following exceptions:
#PyPDF2.utils.PdfReadError
#ValueError
#TypeError (not iterable)
#FileNotFoundError
#OSError (the handle is invalid) (invalid argument)
def preprocess(imgs, save_to):
    if is_usable_as_file(imgs):
        imgs = [imgs]
    else:
        for img in imgs:
            if not is_usable_as_file(img):
                raise ValueError("Received an object that was not a string, bytes, path-like, or a file-like object")
        
        
    converted = [convert_image_to_pdf(img, tempfile.TemporaryFile()) for img in imgs]

    output_pdf = PyPDF2.PdfFileWriter()

    #Well, I TRIED to not keep everything in memory!
    for pdf in converted:
        for page in PyPDF2.PdfFileReader(pdf).pages:
            output_pdf.addPage(page)

    try:
        output_pdf.write(save_to)
    except AttributeError:
        with open(save_to,"wb") as f:
            output_pdf.write(f)

    #I own these tempfiles
    for f in converted:
        f.close()

    return save_to
