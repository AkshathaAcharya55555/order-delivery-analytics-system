package com.orderdelivery.orderservice.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * Read-only reference to the customers table (owned by database/schema.sql,
 * not by this service). Only used here to validate that a customer_id
 * referenced by a new order actually exists.
 */
@Entity
@Table(name = "customers")
public class Customer {

    @Id
    @Column(name = "customer_id")
    private Long customerId;

    @Column(name = "first_name")
    private String firstName;

    @Column(name = "last_name")
    private String lastName;

    protected Customer() {
    }

    public Long getCustomerId() {
        return customerId;
    }

    public String getFirstName() {
        return firstName;
    }

    public String getLastName() {
        return lastName;
    }
}
