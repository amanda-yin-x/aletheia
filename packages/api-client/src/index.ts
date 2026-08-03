import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const createAletheiaClient = (baseUrl: string) => createClient<paths>({ baseUrl });

