package com.orderdelivery.deliveryservice.exception;

/** Thrown when no rider matching the assignment criteria can be found. */
public class NoAvailableRiderException extends RuntimeException {
    public NoAvailableRiderException(String message) {
        super(message);
    }
}
