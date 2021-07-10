from PIL import Image
import tempfile, asyncio, aiogoogle, logging, random

CHARS = "qwertyuiopasdfghjklmnbvcxz1234567890QWERTYUIOPLKJHGFDSAZXCVBNM"

def build_basic_request(gs_file_uri, destination_bucket, features="DOCUMENT_TEXT_DETECTION", batch_size=2000):
    return {
        "requests": [
            {
                "inputConfig": {
                    "gcsSource": {
                        "uri": gs_file_uri
                    },
                    "mimeType": "application/pdf"
                },
                "features": [
                    {
                        "type": features
                    }
                ],
                "outputConfig": {
                    "gcsDestination": {
                        "uri": destination_bucket
                    },
                    #batch_size=2000 : Output all pages into one file
                    "batchSize": batch_size
                }
            }
        ]
    }

async def send_for_ocr(session, request):
    vision = await session.discover("vision", "v1")
    req = vision.images.asyncBatchAnnotate()
    req.json = request
    
    #response
    return await auth.session.as_service_account(req)

def convert_image(f, save_to): Image.open(f).save(save_to, "pdf")

async def create_bucket(session, storage, bucket, project_id):
    #attempt to create the bucket
    req = storage.buckets.insert(project=project_id)
    req.json = {
        "name": bucket,
        "location": "US-WEST1",
        "storageClass": "STANDARD",
        "iamConfiguration": {
            "uniformBucketLevelAccess": {
                "enabled": True
            }
        }
    }

    try:
        resp = await session.as_service_account(req)
    except aiogoogle.excs.HTTPError as e:
        if e.res.status_code == 409 and "already own" in e.res.error_msg:      
            pass #Do nothing, resource already exists
        
        elif e.res.status_code == 403:
            print("Cannot create storage bucket (insufficent permissions)")

        elif e.res.status_code == 409 and "not available" in e.res.error_msg:
            print(f"Cannot create storage bucket (someone else already has a bucket named {bucket})")

        else:
            logging.exception("An exception occured when attempting to create the storage bucket")

def generate_name(name_len=16):
    return "".join(random.choice(CHARS) for _ in range(name_len))

async def get_available_name(session, storage, bucket):
    #Technically, this function should be useless because I'm using a namespace with 62**16 possible names
    req = storage.objects.list(bucket=bucket)
    try:
        resp = await session.as_service_account(req)
    except aiogoogle.excs.HTTPError:
        logging.exception("An exception occured when attempting to list the objects in the storage bucket")

    #Technically, I'm blocking the event loop here
    try:
        while True:
            name = generate_name() + ".pdf"
            for obj in resp["items"]:
                if obj["name"] == name:
                    break

            #for-else only runs if break doesn't get called
            else:
                return name

    #There are no objects in the bucket yet
    except KeyError:
        #I mean, I already generated a name before the exception happened
        return name 

async def upload_file_to_bucket(session, storage, bucket, project_id, f, name):
    f.seek(0)
    
    req = storage.objects.insert(bucket=bucket, name=name, contentEncoding="application/pdf")
    req.data = f.read()


    #I can SEE /upload/storage in the discovery docs
    #I just can't activate it!
    #Well, you CAN always do this...
    req.url = 'https://storage.googleapis.com/upload/storage/' + req.url[39:]
    
    try:
        resp = await session.as_service_account(req)
    except aiogoogle.excs.HTTPError:
        logging.exception("An error occured when uploading an object to the bucket")
        breakpoint()
        print()

async def upload_to_bucket(session, storage, bucket, project_id, f, loop, executor):
    #ensures that the bucket exists in the first place
    await create_bucket(session, storage, bucket, project_id)

    #Start processing the image
    if not loop:
        loop = asyncio.get_running_loop()
        
    with tempfile.TemporaryFile() as tf:
        #Because blocking the event loop is a very bad thing
        await loop.run_in_executor(executor, convert_image, f, tf)

        name = await get_available_name(session, storage, bucket)
        
        await upload_file_to_bucket(session, storage, bucket, project_id, tf, name)

    return name

async def delete_object(session, storage, bucket, obj):
    req = storage.objects.delete(bucket=bucket, object=obj)
    resp = await session.as_service_account(req)
    
async def detect_text_in_file(session, bucket, f, project_id = None, loop = None, executor = None):
    storage = await session.discover("storage", "v1")
                        
    if not project_id:
        project_id = session.service_account_creds.project_id
        
    obj_name = await upload_to_bucket(session, storage, bucket, project_id, f, loop, executor)
    await delete_object(session, storage, bucket, obj_name)
        
if __name__ == "__main__":
    import auth, json, asyncio

    with open("../google-apis-key.json") as f:
        session = auth.SessionManager(json.load(f))
        
    with open("C:/Users/magnu/Downloads/picture.jpg","rb") as f:
        asyncio.run(detect_text_in_file(session, "magnusfulton-com-ocr", f))
