// Basic Auth middleware for Netlify Edge Functions
// Set NETLIFY_AUTH_USER and NETLIFY_AUTH_PASS in your Netlify environment variables

export default async (request: Request, context: any) => {
  // Get credentials from environment variables
  const authUser = Deno.env.get("NETLIFY_AUTH_USER") || "admin";
  const authPass = Deno.env.get("NETLIFY_AUTH_PASS") || "password";

  // Check for Authorization header
  const authHeader = request.headers.get("Authorization");

  if (!authHeader || !authHeader.startsWith("Basic ")) {
    return new Response("Authentication required", {
      status: 401,
      headers: {
        "WWW-Authenticate": 'Basic realm="ASQL Documentation"',
      },
    });
  }

  // Decode credentials
  const base64Credentials = authHeader.split(" ")[1];
  const credentials = atob(base64Credentials);
  const [username, password] = credentials.split(":");

  // Verify credentials
  if (username !== authUser || password !== authPass) {
    return new Response("Invalid credentials", {
      status: 401,
      headers: {
        "WWW-Authenticate": 'Basic realm="ASQL Documentation"',
      },
    });
  }

  // Credentials are valid, continue to the site
  return context.next();
};

