package com.orderdelivery.deliveryservice.exception;

/** Thrown when a requested operation is not valid given current order/delivery state. */
public class InvalidStateException extends RuntimeException {
    public InvalidStateException(String message) {
        super(message);
    }
}
