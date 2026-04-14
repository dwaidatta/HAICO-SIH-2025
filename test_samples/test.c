#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Caesar cipher encode */
void caesar_encode(char *s, int shift) {
    for (int i = 0; s[i]; i++) {
        if (s[i] >= 'a' && s[i] <= 'z')
            s[i] = 'a' + (s[i] - 'a' + shift) % 26;
        else if (s[i] >= 'A' && s[i] <= 'Z')
            s[i] = 'A' + (s[i] - 'A' + shift) % 26;
    }
}

/* Caesar cipher decode */
void caesar_decode(char *s, int shift) {
    caesar_encode(s, 26 - shift);
}

/* Bubble sort */
void bubble_sort(int *arr, int n) {
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int tmp = arr[j];
                arr[j]     = arr[j + 1];
                arr[j + 1] = tmp;
            }
        }
    }
}

/* Recursive factorial */
long long factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

/* Check prime */
int is_prime(int n) {
    if (n < 2) return 0;
    for (int i = 2; i * i <= n; i++)
        if (n % i == 0) return 0;
    return 1;
}

int main(void) {
    /* --- Caesar cipher --- */
    char msg[] = "HelloPolaris";
    printf("[caesar] original : %s\n", msg);
    caesar_encode(msg, 7);
    printf("[caesar] encoded  : %s\n", msg);
    caesar_decode(msg, 7);
    printf("[caesar] decoded  : %s\n", msg);

    /* --- Bubble sort --- */
    int arr[] = {42, 7, 19, 3, 88, 55, 1, 23};
    int n = sizeof(arr) / sizeof(arr[0]);
    bubble_sort(arr, n);
    printf("[sort]   sorted   :");
    for (int i = 0; i < n; i++) printf(" %d", arr[i]);
    printf("\n");

    /* --- Factorial --- */
    for (int i = 1; i <= 7; i++)
        printf("[fact]   %d! = %lld\n", i, factorial(i));

    /* --- Primes up to 30 --- */
    printf("[prime]  primes   :");
    for (int i = 2; i <= 30; i++)
        if (is_prime(i)) printf(" %d", i);
    printf("\n");

    return 0;
}