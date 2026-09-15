package com.orderdelivery.deliveryservice.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;

@Entity
@Table(name = "locations")
public class Location {

    @Id
    @Column(name = "location_id")
    private Long locationId;

    @Column(name = "city")
    private String city;

    @Column(name = "latitude")
    private BigDecimal latitude;

    @Column(name = "longitude")
    private BigDecimal longitude;

    protected Location() {
    }

    public Long getLocationId() {
        return locationId;
    }

    public String getCity() {
        return city;
    }

    public BigDecimal getLatitude() {
        return latitude;
    }

    public BigDecimal getLongitude() {
        return longitude;
    }
}
