package com.orderdelivery.orderservice.exception;

/** Thrown when a requested operation is not valid for the order's current status. */
public class InvalidOrderStateException extends RuntimeException {
    public InvalidOrderStateException(String message) {
        super(message);
    }
}
