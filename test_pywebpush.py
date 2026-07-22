from pywebpush import webpush, WebPushException

vapid_private = "5C4ItfpkKFaJi_CbegTUYdBDM5zfuucF7PpuxqNBNfo"

try:
    print("Testing pywebpush parsing of private key...")
    # Just try to construct the JWT or something that forces it to parse the key
    # If the key is not in the format pywebpush expects, it will throw an error
    print("Key is valid format for pywebpush? Let's check.")
except Exception as e:
    print("Exception:", e)
