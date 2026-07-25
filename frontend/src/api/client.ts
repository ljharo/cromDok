import axios, { AxiosError } from "axios";

// Single Axios instance for the whole app. The session lives in an HttpOnly
// cookie (spec 9.4.1), so we only need `withCredentials` — no token storage.
export const client = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
});

// Any 401 means the session is gone/expired: send the user back to /login,
// unless they are already there (e.g. a failed login attempt).
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    return Promise.reject(error);
  },
);
