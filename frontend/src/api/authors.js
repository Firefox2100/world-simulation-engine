import { apiRequest } from "@/api/client";

export async function fetchAuthors() {
    return apiRequest("/authors");
}

export async function createAuthor(author) {
    return apiRequest("/authors", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(author),
    });
}

export async function updateAuthor(authorId, author) {
    return apiRequest(`/authors/${authorId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(author),
    });
}

export async function deleteAuthor(authorId) {
    await apiRequest(`/authors/${authorId}`, {
        method: "DELETE",
    });
}
