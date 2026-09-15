package com.orderdelivery.orderservice.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * Read-only reference to the locations table. Only used here to validate
 * that a delivery_location_id referenced by a new order actually exists.
 */
@Entity
@Table(name = "locations")
public class Location {

    @Id
    @Column(name = "location_id")
    private Long locationId;

    @Column(name = "city")
    private String city;

    protected Location() {
    }

    public Long getLocationId() {
        return locationId;
    }

    public String getCity() {
        return city;
    }
}
