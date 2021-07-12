import tempfile, asyncio, aiogoogle, logging, random, preprocess

CHARS = "qwertyuiopasdfghjklmnbvcxz1234567890QWERTYUIOPLKJHGFDSAZXCVBNM"

def generate_name(name_len=16):
    return "".join(random.choice(CHARS) for _ in range(name_len))

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

async def upload_to_bucket(session, storage, bucket, project_id, f, name):
    close_f = False
    try:
        f.seek(0)
    except AttributeError:
        f = open(f,"rb")
        close_f = True
        
    req = storage.objects.insert(bucket=bucket, name=name)#, contentEncoding="application/pdf")
    req.data = f.read()

    #I can SEE /upload/storage in the discovery docs
    #I just can't activate it!
    #Well, you CAN always do this...
    req.url = 'https://storage.googleapis.com/upload/storage/' + req.url[39:]
    
    try:
        resp = await session.as_service_account(req)
    except aiogoogle.excs.HTTPError:
        logging.exception("An error occured when uploading an object to the bucket")

    if close_f:
        f.close()

async def upload_files_to_bucket_as_pdf(session, storage, bucket, project_id, f, loop, executor):
    #ensures that the bucket exists in the first place
    await create_bucket(session, storage, bucket, project_id)

    #Start processing the image
    if not loop:
        loop = asyncio.get_running_loop()
        
    with tempfile.TemporaryFile() as tf:
        #Because blocking the event loop is a very bad thing
        await loop.run_in_executor(executor, preprocess.preprocess, f, tf)

        name = await get_available_name(session, storage, bucket)
        
        await upload_to_bucket(session, storage, bucket, project_id, tf, name)

    return name

async def delete_object(session, storage, bucket, name):
    req = storage.objects.delete(bucket=bucket, object=name)
    try:
        resp = await session.as_service_account(req)
    except aiogoogle.excs.HTTPError:
        logging.exception("An exception occured when attempting to delete an object in the storage bucket")


async def download_object(session, storage, bucket, name):
    req = storage.objects.get(bucket=bucket, object=name)
    #"Functions with leading underscores were made to be called out of context" - YakimaProgrammer (TM)(R)(C)(Patent Pending)
    req._add_query_param({"alt":"media"})
    
    try:
        return await session.as_service_account(req)
    except aiogoogle.excs.HTTPError:
        logging.exception("An exception occured when attempting to retrieve an object from the storage bucket")

async def get_output_files(session, storage, bucket, name):
    req = storage.objects.list(bucket=bucket)
    resp = await session.as_service_account(req)
    try:
        files = []
        for obj in resp["items"]:
            if obj["name"].startswith(name) and obj["name"] != name:
                files.append(obj["name"])

        return files
    except KeyError:
        return []
