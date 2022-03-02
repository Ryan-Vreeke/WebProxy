# WebProxy
HTTP/1.0 web proxy with object caching. only supports HTTP GET method.

Accepts HTTP requests, forwards the request to the remote servers, and returns the response data to the client, and saves the response in a Dictionary to be used for a fast response later.

The proxy checks if the request is properly formatted and returns 400 error if it is not. the client request to the proxy must be in their absolute uri form and will be turned into the relative URL+Host header format regardless of how the request was received from the client
