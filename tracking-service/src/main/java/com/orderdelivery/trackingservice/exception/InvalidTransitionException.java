package com.orderdelivery.trackingservice.exception;

/** Thrown when a requested status transition is not legal from the order's current status. */
public class InvalidTransitionException extends RuntimeException {
    public InvalidTransitionException(String message) {
        super(message);
    }
}
